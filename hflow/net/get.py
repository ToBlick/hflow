import jax.numpy as jnp
import numpy as np

from hflow.config import Config, Network
from hflow.net.build import build_colora, build_mlp


def get_network(cfg: Config, data, key):

    unet, hnet = cfg.unet, cfg.hnet

    sols, mu, t = data
    MT = mu.shape[-1] + 1
    M, T, N, D = sols.shape

    if cfg.loss.loss_fn == 'ov':
        x_dim = D
        mu_t_dim = MT
        out_dim = 1
    elif cfg.loss.loss_fn == 'ncsm' or cfg.loss.loss_fn == 'cfm':
        x_dim = D
        mu_t_dim = MT+1  # one more for sigma
        out_dim = D

    period = np.asarray([1.0]*x_dim)

    u_config = {'width': unet.width,
                'layers': unet.layers,
                'activation': unet.activation,
                'last_activation': unet.last_activation,
                'w0': unet.w0,
                'bias': unet.bias,
                'period': period,
                'w_init': unet.w_init,
                }

    h_config = {'width': hnet.width,
                'layers': hnet.layers,
                'activation': hnet.activation,
                'last_activation': hnet.last_activation,
                'w0': hnet.w0,
                'bias': hnet.bias,
                'w_init': hnet.w_init, }

    if cfg.unet.model == 'colora':
        u_fn, h_fn, theta_init, psi_init = build_colora(
            u_config, h_config, x_dim, mu_t_dim, out_dim, rank=unet.rank, key=key, full=unet.full)
        params_init = (psi_init, theta_init)

        def s_fn(t, x, params):
            psi, theta = params
            phi = h_fn(psi, t)
            return jnp.squeeze(u_fn(theta, phi, x))
    elif cfg.unet.model == 'film':
        mlp_layers = ['F' if l == 'C' else l for l in unet.layers]
        u_config['layers'] = mlp_layers

        u_fn, h_fn, theta_init, psi_init = build_colora(
            u_config, h_config, x_dim, mu_t_dim, out_dim, rank=unet.rank, key=key, full=unet.full)
        params_init = (psi_init, theta_init)

        def s_fn(t, x, params):
            psi, theta = params
            phi = h_fn(psi, t)
            return jnp.squeeze(u_fn(theta, phi, x))

    elif cfg.unet.model == 'mlp':

        mlp_layers = ['D' if (l == 'C' or l == 'F')
                      else l for l in unet.layers]
        u_config['layers'] = mlp_layers
        u_fn, params_init = build_mlp(
            u_config, in_dim=x_dim+mu_t_dim, out_dim=out_dim, key=key)

        def s_fn(t, x, params):
            t_x = jnp.concatenate([t, x])
            return jnp.squeeze(u_fn(params, t_x))

    return s_fn, params_init
