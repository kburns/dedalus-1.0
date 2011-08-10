"""parallel support.

Author: J. S. Oishi <jsoishi@gmail.com>
Affiliation: KIPAC/SLAC/Stanford
License:
  Copyright (C) 2011 J. S. Oishi.  All Rights Reserved.

  This file is part of dedalus.

  dedalus is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

try:
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
except:
    print "Cannot import mpi4py. Parallelism disabled" 
    comm = None


def setup_parallel_objs(global_shape, global_len):
    """Helper function for parallel runs. Given a global shape and
    length, it returns a local shape and length.

    inputs
    ------
    global_shape (tuple of int)
    global_length (tuple of reals)

    returns
    -------
    local_shape, local_len (tuple of ints, tuple of reals)

    """
    
    local_shape = (global_shape[0]/comm.Get_size(),) + global_shape[1:]
    
    local_len = (global_len[0]/comm.Get_size(),) + global_len[1:]

    return local_shape, local_len
