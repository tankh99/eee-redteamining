# Explore, Establish, Exploit: Red Teaming Language Models from Scratch

Stephen Casper [scasper@mit.edu](scasper@mit.edu)

Jason Lin

Joe Kwon

Gatlen Culp

Dylan Hadfield-Menell

Read the paper on arXiv: [Explore, Establish, Exploit: Red Teaming Language Models from Scratch](https://arxiv.org/abs/2306.09442).

Check out the [CommonClaim dataset](https://github.com/thestephencasper/common_claim).

```
@misc{casper2023explore,
      title={Explore, Establish, Exploit: Red Teaming Language Models from Scratch}, 
      author={Stephen Casper and Jason Lin and Joe Kwon and Gatlen Culp and Dylan Hadfield-Menell},
      year={2023},
      eprint={2306.09442},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
}
```

<img src=eee_fig.png alt='explore establish exploit framework' width=400 title='Explore Establish Exploit Framework'>

## Setup

This repository contains a modified version of the [trlx library, commmit 18ffb1ae09](https://github.com/CarperAI/trlx/tree/18ffb1ae0980e5a794ce9fc2eeda9f39a01ab2e1) from January 3, 2023. 

All code has been tested with python 3.10.

```
pip install -r requirements.txt

git clone https://github.com/thestephencasper/explore_establish_exploit_llms.git
cd trlx
pip install -e .
cd ..

mkdir models
mkdir data
```

## Run

This repository contains all resources needed to red team the open-source GPT-2-xl in order to elicit toxic outputs. 

The 4 e's:

```
python explore.py
python establish.py
python exploit.py
python evaluate.py
```

Be warned that the final results will be offensive in nature.

Then check the results which will be summarized in `/data/results.txt`
