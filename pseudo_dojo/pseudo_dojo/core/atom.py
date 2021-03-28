# coding: utf-8
"""This module provides objects and helper functions for atomic calculations."""
import collections
import numpy as np

from io import StringIO
from pseudo_dojo.refdata.nist import database as nist_database
from scipy.interpolate import UnivariateSpline
from scipy.integrate import cumtrapz

__version__ = "0.1"
__author__ = "Matteo Giantomassi"
__maintainer__ = "Matteo Giantomassi"

__all__ = [
    "NlkState",
    "QState",
    "AtomicConfiguration",
    "RadialFunction",
    "RadialWaveFunction",
    "plot_aepp",
    "plot_logders",
]

# Helper functions

_char2l = {
    "s": 0,
    "p": 1,
    "d": 2,
    "f": 3,
    "g": 4,
    "h": 5,
    "i": 6,
}


def _asl(obj):
    try:
        return _char2l[obj]
    except KeyError:
        return int(obj)


def states_from_string(confstr):
    """
    Parse a string with an atomic configuration and build a list of `QState` instance.
    """
    states = []
    tokens = confstr.split()

    if tokens[0].startswith("["):
        noble_gas = AtomicConfiguration.neutral_from_symbol(tokens.pop(0)[1:-1])
        states = noble_gas.states

    states.extend(parse_orbtoken(t) for t in tokens)
    return states


def parse_orbtoken(orbtoken):
    import re
    m = re.match(r"(\d+)([spdfghi]+)(\d+)", orbtoken.strip())
    if m:
        return QState(n=m.group(1), l=m.group(2), occ=m.group(3))

    raise ValueError("Don't know how to interpret %s" % str(orbtoken))


class NlkState(collections.namedtuple("NlkState", "n, l, k")):
    """
    Named tuple storing (n,l) or (n,l,k) for relativistic pseudos.
    """
    def __str__(self):
        if self.k is None:
            return "n=%i, l=%i" % (self.n, self.l)
        else:
            return "n=%i, l=%i, k=%i" % self

    @property
    def to_dict(self):
        return {"n": self.n, "l": self.l, "k": self.k}


class QState(collections.namedtuple("QState", "n, l, occ, eig, j, s")):
    """
    This object collects the set of quantum numbers and the physical properties
    associated to a single electron in a spherically symmetric atom.

    .. attributes:

        n: Principal quantum number.
        l: Angular momentum.
        occ: Occupancy of the atomic orbital.
        eig: Eigenvalue of the atomic orbital.
        j: J quantum number. None if spin is a good quantum number.
        s: Spin polarization. None if spin is not taken into account.
    """
    # TODO
    # Spin +1, -1 or 1,2 or 0,1?
    def __new__(cls, n, l, occ, eig=None, j=None, s=None):
        """Intercepts super.__new__ adding type conversion and default values."""
        eig = float(eig) if eig is not None else eig
        j = int(j) if j is not None else j
        s = int(s) if s is not None else s
        return super(QState, cls).__new__(cls, int(n), _asl(l), float(occ), eig=eig, j=j, s=s)

    # Rich comparison support.
    # Note that the ordering is based on the quantum numbers and not on energies!
    #def __gt__(self, other):
    #    if self.has_j:
    #        raise NotImplementedError("")
    #    if self.n != other.n: return self.n > other.n
    #    if self.l != other.l

    #    if self == other:
    #        return False
    #    else:
    #        raise RuntimeError("Don't know how to compare %s with %s" % (self, other))
    #def __lt__(self, other):

    @property
    def has_j(self):
        return self.j is not None

    @property
    def has_s(self):
        return self.s is not None


class AtomicConfiguration(object):
    """Atomic configuration defining the all-electron atom."""
    def __init__(self, Z, states):
        """
        Args:
            Z: Atomic number.
            states: List of :class:`QState` instances.
        """
        self.Z = Z
        self.states = states

    @classmethod
    def from_string(cls, Z, string, has_s=False, has_j=False):
        if not has_s and not has_j:
            # Ex: [He] 2s2 2p3
            states = states_from_string(string)
        else:
            raise NotImplementedError("")

        return cls(Z, states)

    def __str__(self):
        lines = ["%s: " % self.Z]
        lines += [str(state) for state in self]
        return "\n".join(lines)

    def __len__(self):
        return len(self.states)

    def __iter__(self):
        return self.states.__iter__()

    def __eq__(self, other):
        if len(self.states) != len(other.states):
            return False

        return (self.Z == other.Z and
                all(s1 == s2 for s1, s2 in zip(self.states, other.states)))

    def __ne__(self, other):
        return not self == other

    @classmethod
    def neutral_from_symbol(cls, symbol):
        """
        symbol: str or int
            Can be a chemical symbol (str) or an atomic number (int).
        """
        entry = nist_database.get_neutral_entry(symbol)
        states = [QState(n=s[0], l=s[1], occ=s[2]) for s in entry.states]
        return cls(entry.Z, states)

    def copy(self):
        """Shallow copy of self."""
        return AtomicConfiguration(self.Z, [s for s in self.states])

    @property
    def symbol(self):
        """Chemical symbol"""
        return nist_database.symbol_from_Z(self.Z)

    @property
    def spin_mode(self):
        """
        unpolarized: Spin-unpolarized calculation.
        polarized: Spin-polarized calculation.
        """
        for state in self:
            # FIXME
            if state.s is not None and state.s == 2:
                return "polarized"
        return "unpolarized"

    @property
    def echarge(self):
        """Electronic charge (float <0)."""
        return -sum(state.occ for state in self)

    @property
    def isneutral(self):
        """True if self is a neutral configuration."""
        return abs(self.echarge + self.Z) < 1.e-8

    def add_state(self, **qnumbers):
        """Add a list of :class:`QState` instances to self."""
        self._push(QState(**qnumbers))

    def remove_state(self, **qnumbers):
        """Remove a quantum state from self."""
        self._pop(QState(**qnumbers))

    def _push(self, state):
        # TODO check that ordering in the input does not matter!
        if state in self.states:
            raise ValueError("state %s is already in self" % str(state))
        self.states.append(state)

    def _pop(self, state):
        try:
            self.states.remove(state)
        except ValueError:
            raise


class RadialFunction(object):
    """A RadialFunction has a name, a radial mesh and values defined on this mesh."""

    def __init__(self, name, rmesh, values):
        """
        Args:
            name: Name of the function (string).
            rmesh: Iterable with the points of the radial mesh.
            values: Iterable with the values of the function on the radial mesh.
        """
        self.name = name
        self.rmesh = np.ascontiguousarray(rmesh)
        self.values = np.ascontiguousarray(values)
        assert len(self.rmesh) == len(self.values)

    @classmethod
    def from_filename(cls, filename, rfunc_name=None, cols=(0, 1)):
        """
        Initialize the object reading data from filename (txt format).

        Args:
            filename: Path to the file containing data.
            rfunc_name: Optional name for the RadialFunction (defaults to filename)
            cols: List with the index of the columns containing the radial mesh and the values.
        """
        data = np.loadtxt(filename)
        rmesh, values = data[:,cols[0]], data[:,cols[1]]
        name = filename if rfunc_name is None else rfunc_name
        return cls(name, rmesh, values)

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        """Iterate over (rpoint, value)."""
        return iter(zip(self.rmesh, self.values))

    def __getitem__(self, rslice):
        return self.rmesh[rslice], self.values[rslice]

    def __repr__(self):
        return "<%s, name=%s at %s>" % (self.__class__.__name__, self.name, id(self))

    def __str__(self):
        stream = StringIO()
        self.pprint(stream=stream)
        return stream.getvalue()

    #def __add__(self, other):
    #def __sub__(self, other):
    #def __mul__(self, other):

    def __abs__(self):
        return self.__class__(self.rmesh, np.abs(self.values))

    @property
    def to_dict(self):
        return dict(
            name=str(self.name),
            rmesh=list(self.rmesh),
            values=list(self.values),
        )

    def pprint(self, what="rmesh+values", stream=None):
        """pprint method (useful for debugging)"""
        from pprint import pprint
        if "rmesh" in what:
            pprint("rmesh:", stream=stream)
            pprint(self.rmesh, stream=stream)

        if "values" in what:
            pprint("values:", stream=stream)
            pprint(self.values, stream=stream)

    @property
    def rmax(self):
        """Outermost point of the radial mesh."""
        return self.rmesh[-1]

    @property
    def rsize(self):
        """Size of the radial mesh."""
        return len(self.rmesh)

    @property
    def minmax_ridx(self):
        """
        Returns the indices of the values in a list with the maximum and minimum value.
        """
        minimum = min(enumerate(self.values), key=lambda s: s[1])
        maximum = max(enumerate(self.values), key=lambda s: s[1])
        return minimum[0], maximum[0]

    @property
    def inodes(self):
        """"List with the index of the nodes of the radial function."""
        inodes = []
        for i in range(len(self.values)-1):
            if self.values[i] * self.values[i+1] <= 0:
                inodes.append(i)
        return inodes

    @property
    def spline(self):
        """Cubic spline."""
        try:
            return self._spline
        except AttributeError:
            self._spline = UnivariateSpline(self.rmesh, self.values, s=0)
            return self._spline

    @property
    def roots(self):
        """Return the zeros of the spline."""
        return self.spline.roots()

    def derivatives(self, r):
        """Return all derivatives of the spline at the point r."""
        return self.spline.derivatives(r)

    def integral(self):
        r"""
        Cumulatively integrate y(x) using the composite trapezoidal rule.

        Returns:
            `Function1d` with :math:`\int y(x) dx`
        """
        from scipy.integrate import cumtrapz
        integ = cumtrapz(self.values, x=self.rmesh)
        pad_intg = np.zeros(len(self.values))
        pad_intg[1:] = integ

        return self.__class__(self.rmesh, pad_intg)

    def integral3d(self, a=None, b=None):
        """
        Return definite integral of the spline of (r**2 values**2) between two given points a and b
        Args:
            a: First point. rmesh[0] if a is None
            b: Last point. rmesh[-1] if a is None
        """
        a = self.rmesh[0] if a is None else a
        b = self.rmesh[-1] if b is None else b
        r2v2_spline = UnivariateSpline(self.rmesh, (self.rmesh * self.values) ** 2, s=0)

        return r2v2_spline.integral(a, b)

    def ifromr(self, rpoint):
        """The index of the point."""
        for (i, r) in enumerate(self.rmesh):
            if r > rpoint:
                return i-1

        if rpoint == self.rmesh[-1]:
            return len(self.rmesh)
        else:
            raise ValueError("Cannot find %s in rmesh" % rpoint)

    def ir_small(self, abs_tol=0.01):
        """
        Returns the rightmost index where the abs value of the wf becomes greater than abs_tol

        Args:
            abs_tol: Absolute tolerance.

        .. warning::

            Assumes that self.values are tending to zero for r --> infinity.
        """
        for i in range(len(self.rmesh)-1, -1, -1):
            if abs(self.values[i]) > abs_tol:
                break
        return i

    def r2f2_integral(self):
        """
        Cumulatively integrate r**2 f**2(r) using the composite trapezoidal rule.
        """
        integ = cumtrapz(self.rmesh**2 * self.values**2, x=self.rmesh)
        pad_intg = np.zeros(len(self))
        pad_intg[1:] = integ

        return pad_intg

    def r2f_integral(self):
        """
        Cumulatively integrate r**2 f(r) using the composite trapezoidal rule.
        """
        integ = cumtrapz(self.rmesh**2 * self.values, x=self.rmesh)
        pad_intg = np.empty(len(self))
        pad_intg[1:] = integ
        return pad_intg

    def get_intr2j0(self, ecut, numq=3001):
        r"""
        Compute 4\pi\int[(\frac{\sin(2\pi q r)}{2\pi q r})(r^2 n(r))dr].
        """
        qmax = np.sqrt(ecut / 2) / np.pi
        qmesh = np.linspace(0, qmax, num=numq, endpoint=True)
        outs = np.empty(len(qmesh))

        # Treat q == 0. Note that rmesh[0] > 0
        f = 4 * np.pi * self.rmesh**2 * self.values
        outs[0] = cumtrapz(f, x=self.rmesh)[-1]

        for i, q in enumerate(qmesh[1:]):
            twopiqr = 2 * np.pi * q * self.rmesh
            f = 4 * np.pi * (np.sin(twopiqr) / twopiqr) * self.rmesh**2 * self.values
            outs[i+1] = cumtrapz(f, x=self.rmesh)[-1]

        from abipy.core.func1d import Function1D
        ecuts = 2 * np.pi**2 * qmesh**2
        return Function1D(ecuts, outs)


class RadialWaveFunction(RadialFunction):
    """
    Extends :class:`RadialFunction` adding info on the set of quantum numbers.
    and methods specialized for electronic wavefunctions.
    """
    TOL_BOUND = 1.e-10

    def __init__(self, state, name, rmesh, values):
        super(RadialWaveFunction, self).__init__(name, rmesh, values)
        self.state = state

    @property
    def isbound(self):
        """True if self is a bound state."""
        back = min(10, len(self))
        return np.all(np.abs(self.values[-back:]) < self.TOL_BOUND)

    @property
    def to_dict(self):
        d = super(RadialWaveFunction, self).to_dict
        d.update(self.state.to_dict)
        return d


def plot_aepp(ae_funcs, pp_funcs=None, **kwargs):
    """
    Uses Matplotlib to plot the radial wavefunction (AE only or AE vs PP)

    Args:
        ae_funcs: All-electron radial functions.
        pp_funcs: Pseudo radial functions.

    ==============  ==============================================================
    kwargs          Meaning
    ==============  ==============================================================
    title           Title of the plot (Default: None).
    show            True to show the figure (Default: True).
    savefig         'abc.png' or 'abc.eps'* to save the figure to a file.
    ==============  ==============================================================

    Returns:
        `matplotlib` figure.

    """
    title = kwargs.pop("title", None)
    show = kwargs.pop("show", True)
    savefig = kwargs.pop("savefig", None)
    multi_plot = kwargs.pop("multi_plot", False)

    import matplotlib.pyplot as plt
    fig = plt.figure()

    if multi_plot:
        num_funcs = len(ae_funcs) if pp_funcs is None else len(pp_funcs)

        spl_idx = 0
        for (state, ae_phi) in ae_funcs.items():
            if pp_funcs is not None and state not in pp_funcs:
                continue

            spl_idx += 1
            ax = fig.add_subplot(num_funcs, 1, spl_idx)

            if spl_idx == 1 and title:
                ax.set_title(title)

            lines, legends = [], []
            line, = ax.plot(ae_phi.rmesh, ae_phi.values, "-b", linewidth=2.0, markersize=1)

            lines.append(line)
            legends.append("AE: %s" % state)

            if pp_funcs is not None:
                pp_phi = pp_funcs[state]
                line, = ax.plot(pp_phi.rmesh, pp_phi.values, "^r", linewidth=2.0, markersize=4)
                lines.append(line)
                legends.append("PP: %s" % state)

            ax.legend(lines, legends, loc="best", shadow=True)

            # Set yticks and labels.
            ylabel = kwargs.get("ylabel", None)
            if ylabel is not None:
                ax.set_ylabel(ylabel)

            if spl_idx == num_funcs:
                ax.set_xlabel("r [Bohr]")

            ax.grid(True)

    else:
        ax = fig.add_subplot(1, 1, 1)
        ax.set_title(title)

        lines, legends = [], []
        for state, ae_phi in ae_funcs.items():
            if pp_funcs is not None and state not in pp_funcs:
                continue

            line, = ax.plot(ae_phi.rmesh, ae_phi.values, "-b", linewidth=2.0, markersize=1)

            lines.append(line)
            legends.append("AE: %s" % state)

            if pp_funcs is not None:
                pp_phi = pp_funcs[state]
                line, = ax.plot(pp_phi.rmesh, pp_phi.values, "^r", linewidth=2.0, markersize=4)
                lines.append(line)
                legends.append("PP: %s" % state)

        ax.legend(lines, legends, loc="best", shadow=True)

        # Set yticks and labels.
        ylabel = kwargs.get("ylabel", None)
        if ylabel is not None:
            ax.set_ylabel(ylabel)

        ax.set_xlabel("r [Bohr]")
        ax.grid(True)

    if show:
        plt.show()

    if savefig is not None:
        fig.savefig(savefig)

    return fig


def plot_logders(ae_logders, pp_logders, **kwargs):
    """
    Uses matplotlib to plot the logarithmic derivatives.

    Args:
        ae_logders: AE logarithmic derivatives.
        pp_logders: PP logarithmic derivatives.

    ==============  ==============================================================
    kwargs          Meaning
    ==============  ==============================================================
    title           Title of the plot (Default: None).
    show            True to show the figure (Default: True).
    savefig         'abc.png' or 'abc.eps'* to save the figure to a file.
    ==============  ==============================================================

    Returns:
        `matplotlib` figure.
    """
    assert len(ae_logders) == len(pp_logders)
    title = kwargs.pop("title", None)
    show = kwargs.pop("show", True)
    savefig = kwargs.pop("savefig", None)

    import matplotlib.pyplot as plt
    fig = plt.figure()

    num_logds, spl_idx = len(ae_logders), 0

    for state, pp_logd in pp_logders.items():
        spl_idx += 1
        ax = fig.add_subplot(num_logds, 1, spl_idx)

        if spl_idx == 1 and title:
            ax.set_title(title)

        lines, legends = [], []

        ae_logd = ae_logders[state]

        line, = ax.plot(ae_logd.rmesh, ae_logd.values, "-b", linewidth=2.0, markersize=1)
        lines.append(line)
        legends.append("AE logder %s" % state)

        line, = ax.plot(pp_logd.rmesh, pp_logd.values, "^r", linewidth=2.0, markersize=4)
        lines.append(line)
        legends.append("PP logder %s" % state)

        ax.legend(lines, legends, loc="best", shadow=True)

        if spl_idx == num_logds:
            ax.set_xlabel("Energy [Ha]")

        ax.grid(True)

    if show:
        plt.show()

    if savefig is not None:
        fig.savefig(savefig)

    return fig
