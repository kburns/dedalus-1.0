"""
Timers to track code performance.

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

import time
from dedalus.utils.parallelism import com_sys

class Timer(object):

    def __init__(self):
        """
        A simple class that builds a dictionary of functions and
        their cumulative times.

        """

        self.timers = {}

    def __call__(self, func):
        """Decorator to time function execution."""

        def wrapper(*args, **kwargs):
            start = time.time()
            retval = func(*args, **kwargs)
            stop = time.time()
            try:
                self.timers[func.func_name] += (stop-start)
            except KeyError:
                self.timers[func.func_name] = (stop-start)

            return retval
        return wrapper

    def print_stats(self, proc=0):
        """Print cumulative times for functions executed on a specified processor."""

        if com_sys.myproc == proc:
            print
            print "---Timings (proc %i)---" % (proc)
            for k,v in self.timers.iteritems():
                print "%s: %10.5f sec" % (k,v)
            print

timer = Timer()

if __name__ == "__main__":
    timer = Timer()

    @timer
    def sleep_two_sec():
        time.sleep(2.0)

    sleep_two_sec()
    timer.print_stats()
