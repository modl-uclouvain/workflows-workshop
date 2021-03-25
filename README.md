# Single-user Jupyter notebook image for workshops

**Please note that this documentation is just a draft. Some of the instructions may be incomplete.**

This notebook folder contains Dockerfile for a single user notebook image which based on Jupyter docker stack.
In addition to the base notebook, it contains all of the necessary packages for the tools. 
The docker image is suitable for running/testing locally and for deploying it by the jupyterhub on a kubernetes cluster.

## Short description

- Based on the jupyter docker image
- Compiled abinit
- Conda python environments 

## Building/using your own docker image

```bash
git clone https://github.com/modl-uclouvain/workflows-workshop.git
cd workflows-workshop
```

### Building the docker image locally

```bash
docker build -t analytics-workshop:latest .
```

### Testing/Developing the notebooks locally
- Use the following command to run the docker image locally:
  ```bash
  docker run --rm \
             -p 8888:8888 \
             -v $PWD/tutorials:/home/jovyan/tutorials \
             --name analytics-workshop \
             analytics-workshop:latest 
  ```
  Note: Although the `--rm` option is useful, you have to use it very carefully. When you stop the notebook server, you can lose all of your modifications which hasn't been stored into the mounted folder.

- To attach a terminal to the running container, you can use the following command:
  ```bash
  docker exec -it analytics-workshop start.sh
  ```
  
More info: https://jupyter-docker-stacks.readthedocs.io/en/latest/using/common.html?highlight=root#alternative-commands
    
    
### Useful tricks for Linux

- For mounting a folder, you may need to use an absolute path or other tricks if the PWD environmental variable is not accessible in your shell:
  ```bash
  docker run --rm \
             -p 8888:8888  \
             -v /path/for/the/tutorials:/home/jovyan/tutorials  \
             --name workflows-workshop \
             workflows-workshop:latest
  ```
- you may need to change the user id in the container - by adding `--user root` and `-e NB_UID=1001` options to your command - to have access for the mounted folders:
  ```bash
  docker run --rm \
             --user root \
             -e NB_UID=1001 \
             -p 8888:8888  \
             -v $PWD/tutorials:/home/jovyan/tutorials  \
             --name workflows-workshop \
             workflows-workshop:latest
  ```
- you can have a password-less sudo access in the container for debugging by adding `--user root` and `-e GRANT_SUDO=yes` options to your command:
  ```bash
  docker run --rm \
             --user root \
             -e GRANT_SUDO=yes \
             -p 8888:8888  \
             -v $PWD/tutorials:/home/jovyan/tutorials  \
             --name workflows-workshop \
             workflows-workshop:latest
  ```
    
More information about the command line options: https://jupyter-docker-stacks.readthedocs.io/en/latest/using/common.html#notebook-options


## Continuous integration (for future usage)

Each commit triggers a build process on GitLab Runner. Besides the latest tag, there will be a unique tag (same that as the value of the git commit) available for explicitly tracking the version of the notebook for cluster deployment.

### Using the docker image from the registry
1. Install docker on your machine
2. Login to the image repository
    ```bash
    docker login gitlab-registry.mpcdf.mpg.de 
    ```
3. Pull the image:
   ```bash
   docker pull gitlab-registry.mpcdf.mpg.de/nomad-lab/analytics-workshop:<tag> 
   ```
   
4. Create a container:
   ```bash
   docker run -p 8888:8888 \
              -v $PWD/notebook/tutorials:/home/jovyan/tutorials \
              gitlab-registry.mpcdf.mpg.de/nomad-lab/analytics-workshop:<tag>
   ```

Note: The latest tag can be found on the following page:
https://gitlab.mpcdf.mpg.de/nomad-lab/analytics-workshop/container_registry

