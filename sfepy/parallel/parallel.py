"""
Functions for a high-level PETSc-based parallelization.
"""
import numpy as nm

import sys, petsc4py
petsc4py.init(sys.argv)

from petsc4py import PETSc
from mpi4py import MPI

from sfepy.base.base import assert_, output, ordered_iteritems
from sfepy.discrete.common.region import Region
from sfepy.discrete.fem.fe_surface import FESurface

def get_inter_facets(domain, cell_tasks):
    """
    For each couple of neighboring task subdomains get the common boundary
    (interface) facets.
    """
    cmesh = domain.cmesh

    # Facet-to-cell connectivity.
    cmesh.setup_connectivity(cmesh.tdim - 1, cmesh.tdim)
    cfc = cmesh.get_conn(cmesh.tdim - 1, cmesh.tdim)

    # Facet tasks by cells in cfc.
    ftasks = cell_tasks[cfc.indices]

    # Mesh inner and surface facets.
    if_surf = cmesh.get_surface_facets()
    if_inner = nm.setdiff1d(nm.arange(cfc.num, dtype=nm.uint32), if_surf)

    # Facets in two tasks = inter-task region facets.
    if_inter = if_inner[nm.where(ftasks[cfc.offsets[if_inner]]
                                 != ftasks[cfc.offsets[if_inner] + 1])]
    aux = nm.c_[cfc.offsets[if_inter], cfc.offsets[if_inter] + 1]
    inter_tasks = ftasks[aux]

    # Fast version:
    # from sfepy.linalg import argsort_rows
    # ii = argsort_rows(inter_tasks)
    # inter_tasks[ii]
    # if_inter[ii]
    inter_facets = {}
    for ii, (i0, i1) in enumerate(inter_tasks):
        facet = if_inter[ii]

        ntasks = inter_facets.setdefault(i0, {})
        facets = ntasks.setdefault(i1, [])
        facets.append(facet)

        ntasks = inter_facets.setdefault(i1, {})
        facets = ntasks.setdefault(i0, [])
        facets.append(facet)

    return inter_facets

def create_task_dof_maps(field, cell_parts, inter_facets):
    """
    For each task list its inner and interface DOFs of the given field and
    create PETSc numbering that is consecutive in each subdomain.

    For each task, the DOF map has the following structure::

      [inner, [own_inter1, own_inter2, ...], [], n_task_total, task_offset]
    """
    domain = field.domain

    id_map = nm.zeros(field.n_nod, dtype=nm.uint32)

    dof_maps = {}
    count = 0
    inter_count = 0
    for ir, ntasks in ordered_iteritems(inter_facets):

        cregion = Region.from_cells(cell_parts[ir], domain, name='task_%d' % ir)
        domain.regions.append(cregion)
        dofs = field.get_dofs_in_region(cregion)
        rdof_map = dof_maps.setdefault(ir, [None, [], 0, 0])

        inter_dofs = []
        for ic, facets in ordered_iteritems(ntasks):
            cdof_map = dof_maps.setdefault(ic, [None, [], 0, 0])

            name = 'inter_%d_%d' % (ir, ic)
            ii = ir

            region = Region.from_facets(facets, domain, name,
                                        parent=cregion.name)
            region.update_shape()

            inter_dofs.append(field.get_dofs_in_region(region))

            ap = field.ap
            sd = FESurface('surface_data_%s' % region.name, region,
                           ap.efaces, ap.econn, field.region)
            econn = sd.get_connectivity()
            n_facet = econn.shape[0]

            ii2 = max(int(n_facet / 2), 1)

            dr = nm.unique(econn[:ii2])
            ii = nm.where((id_map[dr] == 0))[0]
            n_new = len(ii)
            if n_new:
                rdof_map[1].append(dr[ii])
                rdof_map[2] += n_new
                id_map[dr[ii]] = 1
                inter_count += n_new
                count += n_new

            dc = nm.unique(econn[ii2:])
            ii = nm.where((id_map[dc] == 0))[0]
            n_new = len(ii)
            if n_new:
                cdof_map[1].append(dc[ii])
                cdof_map[2] += n_new
                id_map[dc[ii]] = 1
                inter_count += n_new
                count += n_new

        domain.regions.pop() # Remove the cell region.

        inner_dofs = nm.setdiff1d(dofs, nm.concatenate(inter_dofs))
        n_inner = len(inner_dofs)
        rdof_map[2] += n_inner
        assert_(nm.all(id_map[inner_dofs] == 0))
        id_map[inner_dofs] = 1
        count += n_inner

        rdof_map[0] = inner_dofs

    offset = 0
    for ir, dof_map in ordered_iteritems(dof_maps):
        n_owned = dof_map[2]
        output(n_owned, offset)

        i0 = len(dof_map[0])
        id_map[dof_map[0]] = nm.arange(offset, offset + i0, dtype=nm.uint32)
        for aux in dof_map[1]:
            i1 = len(aux)
            id_map[aux] = nm.arange(offset + i0, offset + i0 + i1,
                                    dtype=nm.uint32)
            i0 += i1

        assert_(i0 == n_owned)

        dof_map[3] = offset
        offset += n_owned

    return dof_maps, id_map

def distribute_field_dofs(field, cell_parts, cell_tasks, comm=None,
                          verbose=False):
    """
    Distribute the owned cells and DOFs of the given field to all tasks.

    The DOFs use the PETSc ordering and are in form of a connectivity, so that
    each task can easily identify them with the DOFs of the original global
    ordering or local ordering.
    """
    if comm is None:
        comm = PETSc.COMM_WORLD

    size = comm.size
    mpi = comm.tompi4py()

    if comm.rank == 0:
        inter_facets = get_inter_facets(field.domain, cell_tasks)

        dof_maps, id_map = create_task_dof_maps(field, cell_parts, inter_facets)

        n_cell_parts = [len(ii) for ii in cell_parts]
        output('numbers of cells in tasks:', n_cell_parts, verbose=verbose)
        assert_(sum(n_cell_parts) == field.domain.mesh.n_el)
        assert_(nm.all(n_cell_parts > 0))

        # Send subdomain data to other tasks.
        for it in xrange(1, size):
            # Send owned cells.
            mpi.send(n_cell_parts[it], it)
            mpi.Send([cell_parts[it], MPI.INTEGER4], it)

            dof_map = dof_maps[it]

            # Send owned petsc_dofs range.
            mpi.send(dof_map[3], it)
            mpi.send(dof_map[3] + dof_map[2], it)

            # Send petsc_dofs of global_dofs.
            global_dofs = field.ap.econn[cell_parts[it]]
            petsc_dofs_conn = id_map[global_dofs]
            mpi.send(petsc_dofs_conn.shape[0], it)
            mpi.send(petsc_dofs_conn.shape[1], it)
            mpi.Send([petsc_dofs_conn, MPI.INTEGER4], it)

        cells = cell_parts[0]
        n_cell = len(cells)

        global_dofs = field.ap.econn[cells]

        if 0 in dof_maps:
            dof_map = dof_maps[0]
            petsc_dofs_range = (dof_map[3], dof_map[3] + dof_map[2])
            petsc_dofs_conn = id_map[global_dofs]

        else:
            petsc_dofs_range = (0, global_dofs.max() + 1)
            petsc_dofs_conn = global_dofs

    else:
        # Receive owned cells.
        n_cell = mpi.recv(source=0)
        cells = nm.empty(n_cell, dtype=nm.int32)
        mpi.Recv([cells, MPI.INTEGER4], source=0)

        # Receive owned petsc_dofs range.
        i0 = mpi.recv(source=0)
        i1 = mpi.recv(source=0)
        petsc_dofs_range = (i0, i1)

        # Receive petsc_dofs of global_dofs.
        n_cell = mpi.recv(source=0)
        n_cdof = mpi.recv(source=0)
        petsc_dofs_conn = nm.empty((n_cell, n_cdof), dtype=nm.int32)
        mpi.Recv([petsc_dofs_conn, MPI.INTEGER4], source=0)

        dof_maps = id_map = None

    if verbose:
        output('n_cell:', n_cell)
        output('cells:', cells)
        output('owned petsc DOF range:', petsc_dofs_range,
               petsc_dofs_range[1] - petsc_dofs_range[0])
        aux = nm.unique(petsc_dofs_conn)
        output('local petsc DOFs (owned + shared):', aux, len(aux))

    return cells, petsc_dofs_range, petsc_dofs_conn, dof_maps, id_map

def get_local_ordering(field_i, petsc_dofs_conn):
    """
    Get PETSc DOFs in the order of local DOFs of the localized field `field_i`.
    """
    petsc_dofs = nm.empty(field_i.n_nod, dtype=nm.int32)
    econn = field_i.ap.econn
    petsc_dofs[econn] = petsc_dofs_conn

    return petsc_dofs

def get_sizes(petsc_dofs_range, n_dof, n_components):
    """
    Get (local, total) sizes of a vector and local equation range.
    """
    drange = tuple(n_components * nm.asarray(petsc_dofs_range))
    n_loc = drange[1] - drange[0]
    n_all_dof = n_dof * n_components
    sizes = (n_loc, n_all_dof)

    return sizes, drange

def expand_dofs(dofs, n_components):
    """
    Expand DOFs to equation numbers.
    """
    edofs = nm.empty(n_components * dofs.shape[0], nm.int32)
    for idof in xrange(n_components):
        aux = n_components * dofs + idof
        edofs[idof::n_components] = aux

    return edofs

def create_petsc_matrix(sizes, mtx=None, comm=None):
    """
    Create and allocate a PETSc matrix.
    """
    if comm is None:
        comm = PETSc.COMM_WORLD

    pmtx = PETSc.Mat()
    pmtx.create(comm)
    pmtx.setType('aij')

    pmtx.setSizes((sizes, sizes))

    if mtx is not None:
        pmtx.setPreallocationCSR((mtx.indptr, mtx.indices))

    pmtx.setUp()

    return pmtx

def apply_ebc_to_matrix(mtx, eq_map):
    """
    Apply to matrix rows: zeros to non-diagonal entries, one to the diagonal.
    """
    ebc_rows = eq_map.eq_ebc

    data, prows, cols = mtx.data, mtx.indptr, mtx.indices
    for ir in ebc_rows:
        for ic in xrange(prows[ir], prows[ir + 1]):
            if (cols[ic] == ir):
                data[ic] = 1.0

            else:
                data[ic] = 0.0

def assemble_to_petsc(pmtx, prhs, mtx, rhs, pdofs, comm):
    """
    Assemble local CSR matrix and right-hand side vector to PETSc counterparts.
    """
    lgmap = PETSc.LGMap().create(pdofs, comm=comm)

    pmtx.setLGMap(lgmap, lgmap)
    pmtx.setValuesLocalCSR(mtx.indptr, mtx.indices, mtx.data,
                           PETSc.InsertMode.ADD_VALUES)
    pmtx.assemble()

    prhs.setLGMap(lgmap)
    prhs.setValuesLocal(nm.arange(len(rhs), dtype=nm.int32), rhs,
                        PETSc.InsertMode.ADD_VALUES)
    prhs.assemble()
