
from dataclasses import dataclass, field
from typing import Any, List, Union

from hydra.core.config_store import ConfigStore
from hydra.types import RunMode
from omegaconf import OmegaConf

from hflow.misc.misc import epoch_time, unique_id

SWEEP = {
    # 'problem': 'vtwo,vbump',
    # 'loss.loss_fn': 'ov',
    # 'optimizer.iters': '25_000,50_000,100_000',
    # 'loss.sigma': '5e-3,1e-2,5e-2',



    'problem': 'trap2',
    'loss.loss_fn': 'ov',
    'optimizer.iters': '10_000,25_000',
    'loss.sigma': '0.0,1e-3,5e-3,1e-2',
    'loss.t_batches': '2',

    # 'sample.bs_n': '256,512',
    # 'loss.sigma': '1e-2',
    # 'data.dim': '3',
    # 'sample.bs_n':  '256',
    # 'loss.noise': '0.0,1e-1',
    # 'loss.sigma': '0.0,5e-4,1e-3,5e-3,1e-2,5e-2,1e-1',
    # 'hnet.width': '15,32',
    # 'unet.width': '64,120',
    # 'loss.n_batches': '8',
    # 'loss.t_batches': '8',
    # 'sample.bs_n':  '128',
    # 'sample.bs_t':  '256',
    # 'unet.last_activation': 'none,tanh'

}

SLURM_CONFIG = {
    'timeout_min': 60*4,
    'cpus_per_task': 4,
    'mem_gb': 50,
    # 'gpus_per_node': 1,
    'gres': 'gpu'
}


@dataclass
class Network:
    model: str = 'colora'
    width: int = 64
    layers: List[str] = field(default_factory=lambda: [
                              'C']*7)  # ['P',*['C']*7])
    activation: str = 'swish'
    rank: int = 3
    full: bool = True
    bias: bool = True
    last_activation: Union[str, None] = 'none'
    w0: float = 8.0
    w_init: str = 'lecun'


@dataclass
class Optimizer:
    lr: float = 2e-3
    iters: int = 25_000
    scheduler: bool = True
    optimizer: str = 'adam'


@dataclass
class Data:
    ode: str = 'euler'
    dt: float = 5e-3
    t_end: float = 10
    n_samples: int = 10_000
    normalize: bool = True
    save: bool = False
    load: bool = False
    dim: Union[int, None] = None


@dataclass
class Loss:
    loss_fn: str = 'ov'
    noise: float = 0.0
    sigma: float = 1e-1
    log: bool = False
    trace: str = 'hutch'
    L: int = 10
    t_batches: int = 1
    n_batches: int = 1


@dataclass
class Sample:
    bs_n: int = 256
    bs_t: int = 256
    scheme_t: str = 'gauss'
    scheme_n: str = 'traj'


@dataclass
class Test:
    run: bool = True
    dt: float = 1e-3
    t_samples: Union[int, None] = 128
    n_samples: int = 20_000
    n_plot_samples: int = 2000
    plot_particles: bool = False
    plot_hist: bool = False
    plot_func: bool = False
    w_eps: float = 0.01
    noise_type: str = 'sde'
    electric: bool = False
    save_sol: bool = False
    mean: bool = False
    wass: bool = False


@dataclass
class Config:

    problem: str

    unet: Network = field(default_factory=Network)
    hnet: Network = field(
        default_factory=lambda: Network(width=15, layers=['D']*3))
    optimizer: Optimizer = field(default_factory=Optimizer)
    data: Data = field(default_factory=Data)

    loss: Loss = field(default_factory=Loss)

    test: Test = field(default_factory=Test)
    sample: Sample = field(default_factory=Sample)

    # misc
    name: str = field(default_factory=lambda: epoch_time(2))
    x64: bool = False  # whether to use 64 bit precision in jax
    platform: Union[str, None] = None  # gpu or cpu, None will let jax default
    # output_dir: str = './results/${hydra.job.name}'  # where to save results, if None nothing is saved

    seed: int = 1
    debug_nans: bool = False  # weather to debug nans
    # optional info about details of the experiment
    info: Union[str, None] = None

    # hydra config configuration
    hydra: Any = field(default_factory=lambda: hydra_config)
    defaults: List[Any] = field(default_factory=lambda: defaults)


##########################
## hydra settings stuff ##
##########################
defaults = [
    # https://hydra.cc/docs/tutorials/structured_config/defaults/
    # "_self_",
    {"override hydra/launcher": "submitit_slurm"},
    # add color logging
    {"override hydra/job_logging": "colorlog"},
    {"override hydra/hydra_logging": "colorlog"}
]


# def get_mode():
#     if len(SWEEP.keys()) > 0:
#         return RunMode.MULTIRUN
#     return RunMode.RUN


hydra_config = {
    # sets the out dir from config.problem and id
    "run": {
        "dir": "results/${problem}/single/${name}"
    },
    "sweep": {
        "dir": "results/${problem}/multi/${name}"
    },

    # "mode": get_mode(),
    "sweeper": {
        "params": {
            **SWEEP
        }
    },
    # https://hydra.cc/docs/1.2/plugins/submitit_launcher/
    "launcher": {
        **SLURM_CONFIG
    },
    # sets logging config
    "job_logging": {
        "formatters": {
            "colorlog": {
                "format": '[%(levelname)s] - %(message)s'
            }
        }
    },
    "job": {
        "env_set": {
            "XLA_PYTHON_CLIENT_PREALLOCATE": "false"
        }
    }
}


##################################
## problem wise default configs ##
##################################


cs = ConfigStore.instance()
cs.store(name="default", node=Config)

vlasov_config = Config(problem='vtwo',
                       loss=Loss(sigma=1e-2),
                       data=Data(t_end=40, n_samples=25_000, dt=1e-2),
                       test=Test(plot_hist=True, electric=True, wass=True, n_samples=25_000))


osc_config = Config(problem='bi',
                    data=Data(t_end=12, dt=1e-2, n_samples=25_000),
                    test=Test(plot_particles=True, mean=True, wass=True))


trap_config = Config(problem='trap',
                     data=Data(t_end=2, dim=100, n_samples=5000, dt=7.5e-3),
                     sample=Sample(bs_n=256, bs_t=256),
                     test=Test(plot_particles=True, mean=True))

trap2_config = Config(problem='trap2',
                      loss=Loss(sigma=1e-2),
                      data=Data(t_end=1, dim=100, n_samples=5000, dt=4e-3),
                      sample=Sample(bs_n=256, bs_t=256),
                      test=Test(plot_particles=True, mean=True))

mdyn_config = Config(problem='mdyn',
                     data=Data(t_end=1, dim=2, n_samples=10_000, dt=2e-3),
                     test=Test(plot_particles=True, wass=True))

lz9_config = Config(problem='lz9',
                    data=Data(t_end=20, n_samples=10_000, dt=1e-2),
                    loss=Loss(sigma=5e-2),
                    test=Test(plot_particles=True, wass=True, mean=True))

cs.store(name="lz9", node=lz9_config)
cs.store(name="mdyn", node=mdyn_config)
cs.store(name="trap", node=trap_config)
cs.store(name="trap2", node=trap2_config)
cs.store(name="osc", node=osc_config)
cs.store(name="vlasov", node=vlasov_config)
