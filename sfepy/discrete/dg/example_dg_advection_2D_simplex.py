import numpy as nm
import matplotlib.pyplot as plt


# sfepy imports
from sfepy.discrete.fem import Mesh
from sfepy.discrete.fem.meshio import UserMeshIO
from sfepy.base.base import Struct
from sfepy.base.base import IndexedStruct
from sfepy.discrete import (FieldVariable, Material, Integral, Function,
                            Equation, Equations, Problem)
from sfepy.discrete.fem import Mesh, FEDomain, Field
from sfepy.discrete.conditions import InitialCondition, EssentialBC, Conditions
from sfepy.terms.terms import Term
from sfepy.solvers.ls import ScipyDirect
from sfepy.solvers.nls import Newton
from sfepy.solvers.ts_solvers import SimpleTimeSteppingSolver
from sfepy.mesh.mesh_generators import gen_block_mesh
from sfepy.mesh.mesh_tools import triangulate
from sfepy.discrete.fem.meshio import VTKMeshIO

from sfepy.base.conf import ProblemConf

# local import
from dg_terms import AdvFluxDGTerm, AdvVolDGTerm
# from dg_equation import Equation
from dg_tssolver import EulerStepSolver, DGTimeSteppingSolver, RK3StepSolver
from dg_field import DGField

from my_utils.inits_consts import left_par_q, gsmooth, const_u, ghump, superic
from my_utils.visualizer import load_vtks, plot1D_DG_sol

mesh = gen_block_mesh((1., 1.), (10, 10), (0., 0.))
mesh = triangulate(mesh)
outfile =  "output/mesh/simp_1D_mesh.vtk"
meshio = VTKMeshIO(outfile)
# meshio.write(outfile, mesh)

domain = FEDomain('domain', mesh)
omega = domain.create_region('Omega', 'all')
integral = Integral('i', order=5)


approx_order = 2

fefield = Field.from_args('fu', nm.float64, 'scalar', omega, approx_order=approx_order)

u = FieldVariable('u', 'unknown', fefield, history=1)
v = FieldVariable('v', 'test', fefield, primary_var_name='u')
# fefield.get_mapping(omega, integral, "volume")

dgfield = DGField('dgfu', nm.float64, 'scalar', omega,
                  approx_order=approx_order)

dgu = FieldVariable('u', 'unknown', dgfield, history=1)
dgv = FieldVariable('v', 'test', dgfield, primary_var_name='u')