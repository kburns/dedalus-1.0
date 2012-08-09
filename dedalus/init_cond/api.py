"""API for initial conditions

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

from .init_cond import \
    taylor_green, \
    sin_k, \
    cos_k, \
    turb, \
    turb_new, \
    MIT_vortices, \
    vorticity_wave, \
    collisionless_cosmo_fields, \
    cosmo_fields, \
    cosmo_spectra, \
    alfven, \
    zeldovich, \
    kida_vortex

from .turb_spectra import \
    mcwilliams_spec
