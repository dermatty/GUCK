cd /media/nfs/development/GIT/GUCK/bin/guck
OS=$(cat /etc/os-release | sed '2q;d')

if [ "$OS" == "ID=ubuntu" ]; then
   # cuda 8.0
   # virtualenv
   export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3
   export WORKON_HOME=$HOME/.virtualenvs
   source /usr/local/bin/virtualenvwrapper.sh
   export PATH=/usr/local/cuda-8.0/bin${PATH:+:${PATH}}
   export LD_LIBRARY_PATH=/usr/local/cuda-8.0/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
   export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/cuda-8.0/extras/CUPTI/lib64"
   export LD_LIBRARY_PATH=/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
   export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/usr/local/cuda/extras/CUPTI/lib64"
   export CUDA_HOME=/usr/local/cuda
fi

if [ "$OS" == "ID=arch" ]; then
	# virtualenvwrapper
	export WORKON_HOME=~/.virtualenvs
	source /usr/bin/virtualenvwrapper.sh

	export CUDA_HOME=/opt/cuda
	export PATH=$PATH:/opt/cuda/bin
	export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/cuda/lib64
	export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/cuda/extras/CUPTI/lib64
	export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
fi

if [ "$OS" == "ID=gentoo" ]; then
        # virtualenvwrapper
        export WORKON_HOME=~/.virtualenvs
        source /usr/bin/virtualenvwrapper.sh

        export CUDA_HOME=/opt/cuda
        export PATH=$PATH:/opt/cuda/bin
        export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/cuda/lib64
        export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/cuda/extras/CUPTI/lib64
        export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
fi

/home/stephan/.virtualenvs/cvp0/bin/python /media/nfs/development/GIT/GUCK/bin/guck/guck.py



