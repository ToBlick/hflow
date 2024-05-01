from functools import partial

import jax
import jax.numpy as jnp
import numpy as np
from einops import rearrange
from jax import vmap
from jax.experimental.host_callback import id_print
from scipy.interpolate import RegularGridInterpolator

import hflow.io.result as R
from hflow.config import Sample
from hflow.io.utils import log
from hflow.misc.jax import get_rand_idx
from hflow.misc.misc import (gauss_quadrature_weights_points,
                             pts_array_from_space)


def get_arg_fn(sample_cfg: Sample, data):
    log.info("gettings samples...")
    sols, mu_data, t_data = data
    bs_t = sample_cfg.bs_t
    quad_weights = None
    M, T, N, D = sols.shape
    bs_t = min(sample_cfg.bs_t, T)
    bs_n = min(sample_cfg.bs_n, N)
    sols = rearrange(sols, 'M T N D -> T M N D')
    t_data = t_data / t_data[-1]
    if sample_cfg.scheme_t == 'gauss':

        g_pts_01, quad_weights = gauss_quadrature_weights_points(
            bs_t, a=0.0, b=1.0)

        start, end = jnp.asarray([0]), jnp.asarray([1.0])
        g_pts_01 = jnp.concatenate([start, g_pts_01, end])
        # interp
        sols = interplate_in_t(sols, t_data, g_pts_01)
        t_data = g_pts_01

    elif sample_cfg.scheme_t == 'piece':

        pts_per_seg = bs_t
        segs = bs_t // pts_per_seg

        t_split = jnp.array_split(t_data, segs)
        quad_weights = []
        t_gauss = []

        for t_sl in t_split:
            g_pts_t, qw = gauss_quadrature_weights_points(
                pts_per_seg, a=t_sl[0], b=t_sl[-1])
            t_gauss.append(g_pts_t)
            quad_weights.append(qw)

        start, end = jnp.asarray([0]), jnp.asarray([1.0])
        g_pts_01 = jnp.concatenate([start, *t_gauss, end])
        quad_weights = jnp.concatenate(quad_weights)

        # interp
        sols = interplate_in_t(sols, t_data, g_pts_01)
        t_data = g_pts_01

    elif sample_cfg.scheme_t == 'equi':
        g_pts_01 = jnp.linspace(0.0, 1.0, bs_t+2)
        sols = interplate_in_t(sols, t_data, g_pts_01)
        t_data = g_pts_01

    sols = rearrange(sols, 'T M N D -> M T N D')
    log.info(f'sample shape {sols.shape}')
    args_fn = get_data_fn(sols, mu_data, t_data, quad_weights,
                          bs_n, bs_t, sample_cfg.scheme_t, sample_cfg.scheme_n)

    return args_fn


def get_data_fn(sols, mu_data, t_data, quad_weights, bs_n, bs_t, scheme_t, scheme_n):
    M, T, N, D = sols.shape
    t_data = t_data.reshape(-1, 1)

    sols = jnp.asarray(sols)
    mu_data = jnp.asarray(mu_data)
    t_data = jnp.asarray(t_data)

    def args_fn(key, percent):

        nonlocal sols
        nonlocal t_data

        keyn, keym, keyt = jax.random.split(key, num=3)

        m_idx = jax.random.randint(keym, minval=0, maxval=M, shape=())
        mu_sample = mu_data[m_idx]
        sols_sample = sols[m_idx]

        if scheme_t == 'rand':
            t_idx = jax.random.choice(keyt, T-1, shape=(bs_t,), replace=False)
            start, end = jnp.asarray([0]), jnp.asarray([T-1])
            t_idx = jnp.concatenate([start, t_idx, end])
            t_sample = t_data[t_idx]
            sols_sample = sols_sample[t_idx]
        elif scheme_t == 'seq':
            end = T-1

            # if percent < 0.25:
            #     t_sample = t_data

            # else:
            # print(percent)
            groups = jnp.linspace(0.2, 1, 10)
            closest = groups[jnp.argmin(jnp.abs(groups-percent))]
            end = int(min(end*closest, end))
            # t_sample = t_data[:end]
            # sols_sample = sols_sample[:end]

            t_idx = jax.random.choice(keyt, end, shape=(bs_t,), replace=False)
            start, end = jnp.asarray([0]), jnp.asarray([end])
            t_idx = jnp.concatenate([start, t_idx, end])
            t_sample = t_data[t_idx]

            # t_sample = jnp.linspace(0, 1, len(t_sample)).reshape(-1, 1)
            sols_sample = sols_sample[t_idx]

        else:
            t_sample = t_data

        if scheme_n == 'rand':
            keys = jax.random.split(keyn, num=bs_t+2)
            sample_idx = vmap(get_rand_idx, (0, None, None))(keys, N, bs_n)
            sols_sample = sols_sample[jnp.arange(len(sols_sample))[
                :, None], sample_idx]
        else:
            idx = get_rand_idx(keyn, N, bs_n)
            sols_sample = sols_sample[:, idx]

        return sols_sample, mu_sample, t_sample, quad_weights

    return args_fn


def interplate_in_t(sols, true_t, interp_t):
    sols = np.asarray(sols)
    T, M, N, D = sols.shape

    data_spacing = [np.linspace(0.0, 1.0, n) for n in sols.shape[1:]]
    spacing = [np.squeeze(true_t), *data_spacing]

    gt_f = RegularGridInterpolator(
        spacing, sols, method='linear', bounds_error=True)

    interp_spacing = [np.squeeze(interp_t), *data_spacing]
    x_pts = pts_array_from_space(interp_spacing)
    interp_sols = gt_f(x_pts)

    interp_sols = rearrange(interp_sols, '(T M N D) -> T M N D', M=M, N=N, D=D)
    return interp_sols
