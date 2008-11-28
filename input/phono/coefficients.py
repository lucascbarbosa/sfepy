from sfepy.fem.periodic import *

def define_input( filename, region, dim, geom ):
    """Uses materials, fe of master file, merges regions."""
    filename_mesh = filename
    
    coefs = {
        'E' : {'requires' : ['pis', 'corrs_phono_rs'],
               'variables' : ['Pi1', 'Pi2'],
               'region' : region,
               'expression' : 'dw_lin_elastic.i2.%s( matrix.D, Pi1, Pi2 )' \
               % region},
    }

    all_periodic = ['periodic_%s' % ii for ii in ['x', 'y', 'z'][:dim] ]
    requirements = {
        'pis' : {
            'variables' : ['u1'],
        },
        'corrs_phono_rs' : {
             'variables' : ['u1', 'v1', 'Pi'],
             'ebcs' : ['fixed_u'],
             'epbcs' : all_periodic,
             'equations' : {'eq' : """dw_lin_elastic.i2.%s( matrix.D, v1, u1 )
                            + dw_lin_elastic.i2.%s( matrix.D, v1, Pi ) = 0""" \
                            % (region, region)},
        
        },
    }

    integral_1 = {
        'name' : 'i2',
        'kind' : 'v',
        'quadrature' : 'gauss_o3_d%d' % dim,
    }

    field_10 = {
        'name' : 'displacement_matrix',
        'dim' : (dim,1),
        'domain' : region,
        'bases' : {region : '%s_P1' % geom}
    }

    variables = {
        'u1' : ('unknown field', 'displacement_matrix', 0),
        'v1' : ('test field', 'displacement_matrix', 'u1'),
        'Pi' : ('parameter field', 'displacement_matrix', 'u1'),
        'Pi1' : ('parameter field', 'displacement_matrix', 'u1'),
        'Pi2' : ('parameter field', 'displacement_matrix', 'u1'),
    }

    if filename.find( 'mesh_circ21' ) >= 0:
        wx = 0.499
        wy = 0.499
    elif filename.find( 'cube_cylinder_centered' ) >= 0:
        wx = 0.499
        wy = 0.499
        wz = 0.499

    ebcs = {
        'fixed_u' : ('Corners', {'u1.all' : 0.0}),
    }

    ##
    # Periodic boundary conditions.
    if dim == 3:
        regions = {
            'Near' : ('nodes in (y < -%.3f)' % wy, {}),
            'Far' : ('nodes in (y > %.3f)' % wy, {}),
            'Bottom' : ('nodes in (z < -%.3f)' % wz, {}),
            'Top' : ('nodes in (z > %.3f)' % wz, {}),
            'Left' : ('nodes in (x < -%.3f)' % wx, {}),
            'Right' : ('nodes in (x > %.3f)' % wx, {}),
            'Corners' : ("""nodes in
                            ((x < -%.3f) & (y < -%.3f) & (z < -%.3f))
                          | ((x >  %.3f) & (y < -%.3f) & (z < -%.3f))
                          | ((x >  %.3f) & (y >  %.3f) & (z < -%.3f))
                          | ((x < -%.3f) & (y >  %.3f) & (z < -%.3f))
                          | ((x < -%.3f) & (y < -%.3f) & (z >  %.3f))
                          | ((x >  %.3f) & (y < -%.3f) & (z >  %.3f))
                          | ((x >  %.3f) & (y >  %.3f) & (z >  %.3f))
                          | ((x < -%.3f) & (y >  %.3f) & (z >  %.3f))
                          """ % ((wx, wy, wz) * 8), {}),
        }
        epbc_10 = {
            'name' : 'periodic_x',
            'region' : ['Left', 'Right'],
            'dofs' : {'u1.all' : 'u1.all'},
            'match' : 'match_x_plane',
        }
        epbc_11 = {
            'name' : 'periodic_y',
            'region' : ['Near', 'Far'],
            'dofs' : {'u1.all' : 'u1.all'},
            'match' : 'match_y_plane',
        }
        epbc_12 = {
            'name' : 'periodic_z',
            'region' : ['Top', 'Bottom'],
            'dofs' : {'u1.all' : 'u1.all'},
            'match' : 'match_z_plane',
        }
    else:
        regions = {
            'Bottom' : ('nodes in (y < -%.3f)' % wy, {}),
            'Top' : ('nodes in (y > %.3f)' % wy, {}),
            'Left' : ('nodes in (x < -%.3f)' % wx, {}),
            'Right' : ('nodes in (x > %.3f)' % wx, {}),
            'Corners' : ("""nodes in
                              ((x < -%.3f) & (y < -%.3f))
                            | ((x >  %.3f) & (y < -%.3f))
                            | ((x >  %.3f) & (y >  %.3f))
                            | ((x < -%.3f) & (y >  %.3f))
                            """ % ((wx, wy) * 4), {}),
        }
        epbc_10 = {
            'name' : 'periodic_x',
            'region' : ['Left', 'Right'],
            'dofs' : {'u1.all' : 'u1.all'},
            'match' : 'match_y_line',
        }
        epbc_11 = {
            'name' : 'periodic_y',
            'region' : ['Top', 'Bottom'],
            'dofs' : {'u1.all' : 'u1.all'},
            'match' : 'match_x_line',
        }

    solver_0 = {
        'name' : 'ls',
        'kind' : 'ls.umfpack', # Direct solver.
    }

    solver_1 = {
        'name' : 'newton',
        'kind' : 'nls.newton',

        'i_max'      : 2,
        'eps_a'      : 1e-8,
        'eps_r'      : 1e-2,
        'macheps'   : 1e-16,
        'lin_red'    : 1e-2, # Linear system error < (eps_a * lin_red).
        'ls_red'     : 0.1,
        'ls_red_warp' : 0.001,
        'ls_on'      : 0.99999,
        'ls_min'     : 1e-5,
        'check'     : 0,
        'delta'     : 1e-6,
        'is_plot'    : False,
        'problem'   : 'nonlinear', # 'nonlinear' or 'linear' (ignore i_max)
    }

    return locals()
