#create KubeTerminal Linux executable

FROM ubuntu:16.04

RUN apt-get update
RUN apt -y install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev wget
RUN apt-get install -y python3-dev
RUN apt-get install -y python-dev

WORKDIR /python-src

RUN wget https://www.python.org/ftp/python/3.8.1/Python-3.8.1.tgz
RUN tar -xf Python-3.8.1.tgz

WORKDIR /python-src/Python-3.8.1 
RUN ./configure --enable-optimizations --enable-shared
RUN make -j $(nproc)
RUN make altinstall

# RUN python3.8 --version
#RUN export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib/python3.8/:/usr/local/lib/
ENV LD_LIBRARY_PATH /usr/local/lib/python3.8/:/usr/local/lib/
RUN python3.8 -m pip install prompt_toolkit
RUN python3.8 -m pip install pyinstaller
RUN python3.8 -m pip install ascii_graph
RUN python3.8 -m pip install pyperclip

WORKDIR /root

COPY kubeterminal.py .
COPY application/ ./application/
COPY kubectl/ ./kubectl/

RUN pyinstaller --onefile kubeterminal.py

CMD ["/bin/bash"]