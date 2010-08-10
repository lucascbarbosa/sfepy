"""
Linear elasticity with pressure traction load on a surface and
constrained to one-dimensional motion.
"""
import numpy as nm

def linear_tension(ts, coor, mode=None, region=None, ig=None):
    if mode == 'qp':
        val = nm.tile(1.0, (coor.shape[0], 1, 1))

        return {'val' : val}

def define():
    """Define the problem to solve."""
    from sfepy import data_dir

    filename_mesh = data_dir + '/meshes/3d/block.mesh'

    options = {
        'nls' : 'newton',
        'ls' : 'ls',
    }

    functions = {
        'linear_tension' : (linear_tension,),
    }

    fields = {
        'displacement': ('real', 3, 'Omega', 1),
    }

    materials = {
        'solid' : ({
            'lam' : 5.769,
            'mu' : 3.846,
        },),
        'load' : (None, 'linear_tension')
    }

    variables = {
        'u' : ('unknown field', 'displacement', 0),
        'v' : ('test field', 'displacement', 'u'),
    }

    regions = {
        'Omega' : ('all', {}),
        'Left' : ('nodes in (x < -4.99)', {}),
        'Right' : ('nodes in (x > 4.99)', {}),
    }

    ebcs = {
        'fixb' : ('Left', {'u.all' : 0.0}),
        'fixt' : ('Right', {'u.[1,2]' : 0.0}),
    }

    ##
    # Balance of forces.
    equations = {
        'elasticity' :
        """dw_lin_elastic_iso.2.Omega( solid.lam, solid.mu, v, u )
         = - dw_surface_ltr.2.Right( load.val, v )""",
    }

    ##
    # Solvers etc.
    solvers = {
        'ls' : ('ls.scipy_direct', {}),
        'newton' : ('nls.newton',
                    { 'i_max'      : 1,
                      'eps_a'      : 1e-10,
                      'eps_r'      : 1.0,
                      'macheps'   : 1e-16,
                      # Linear system error < (eps_a * lin_red).
                      'lin_red'    : 1e-2,                
                      'ls_red'     : 0.1,
                      'ls_red_warp' : 0.001,
                      'ls_on'      : 1.1,
                      'ls_min'     : 1e-5,
                      'check'     : 0,
                      'delta'     : 1e-6,
                      'is_plot'    : False,
                      # 'nonlinear' or 'linear' (ignore i_max)
                      'problem'   : 'nonlinear'}),
    }

    ##
    # FE assembling parameters.
    fe = {
        'chunk_size' : 1000,
        'cache_override' : False,
    }

    return locals()
