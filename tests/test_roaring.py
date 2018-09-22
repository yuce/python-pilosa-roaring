# Copyright 2018 Pilosa Corp.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived
# from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.
#

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.split(os.path.dirname(os.path.abspath(__file__)))[0])
from roaring.roaring import Container, Bitmap, ARRAY_MAX_SIZE

class ContainerTestCase(unittest.TestCase):

    def test_iterate(self):
        c = Container()
        c.add(10)
        target = [10]
        self.assertEqual(target, list(c))
        c.add(42)
        target = [10, 42]
        self.assertEqual(target, list(c))
        for i in range(ARRAY_MAX_SIZE + 1):
            c.add(i)
        target = list(range(ARRAY_MAX_SIZE + 1))
        self.assertEqual(target, list(c))
        self.assertEqual(c.type, c.TYPE_BITMAP)

    def test_iterate_invalid_container(self):
        c = Container()
        c.type = 42
        self.assertRaises(Exception, list, c.__iter__())

    def test_to_runs(self):
        from roaring.roaring import to_runs
        self.assertEqual([], to_runs(iter([])))
        self.assertEqual([(1, 1)], to_runs(iter([1])))
        self.assertEqual([(1, 2)], to_runs(iter([1, 2])))
        self.assertEqual([(1, 3)], to_runs(iter([1, 2, 3])))
        self.assertEqual([(1, 3), (5, 5)], to_runs(iter([1, 2, 3, 5])))
        self.assertEqual([(1, 3), (5, 6)], to_runs(iter([1, 2, 3, 5, 6])))
        self.assertEqual([(1, 3), (5, 5), (7, 7)], to_runs(iter([1, 2, 3, 5, 7])))

    def test_rle(self):
        c = Container()
        for i in range(5):
            c.add(i)
        c.add(10)
        c.add(20)
        for i in range(30, 34):
            c.add(i)
        c._convert_to_runs()
        self.assertEqual(c.type, Container.TYPE_RLE)
        runs_target = [(0, 4), (10, 10), (20, 20), (30, 33)]
        self.assertEqual(runs_target, c.runs)
        iterate_target = [0, 1, 2, 3, 4, 10, 20, 30, 31, 32, 33]
        self.assertEqual(iterate_target, list(c))

    def test_serialization_cost_calculation(self):
        bits = [0, 1, 2, 3, 4, 10, 20, 30, 31, 32, 33]
        c = Container()
        for bit in bits:
            c.add(bit)
        self.assertEqual(Container.TYPE_ARRAY, c.type)
        self.assertEqual(88, c._serialization_cost())

        c._convert_to_bitmap()
        self.assertEqual(Container.TYPE_BITMAP, c.type)
        self.assertEqual(8, c._serialization_cost())

        c._convert_to_runs()
        self.assertEqual(Container.TYPE_RLE, c.type)
        self.assertEqual(66, c._serialization_cost())

    def test_optimize(self):
        c = Container()
        for i in range(ARRAY_MAX_SIZE):
            c.add(i)
        opt_c = c._optimized()
        self.assertEqual(Container.TYPE_RLE, opt_c.type)
        self.assertEqual([(0, ARRAY_MAX_SIZE - 1)], opt_c.runs)


class BitmapTestCase(unittest.TestCase):

    def test_bitmap_add(self):
        bmp = Bitmap()
        # force the underlying container to be a bitmap
        target = list(range(ARRAY_MAX_SIZE + 1))
        for i in target:
            bmp.add(i)
        self.assertEqual(target, list(bmp))

        bmp = Bitmap()
        target = list(range(2**16))
        bmp.add(42)  # the same bit below
        for i in target:
            bmp.add(i)
        self.assertEqual(target, list(bmp))

        bmp = Bitmap()
        target = list(range(2**32, 2**32 + 10))
        for i in target:
            bmp.add(i)
        self.assertEqual(target, list(bmp))

        bmp = Bitmap()
        target = list(range(2**32, 2**32 + ARRAY_MAX_SIZE + 1))
        for i in target:
            bmp.add(i)
        self.assertEqual(target, list(bmp))

        bmp = Bitmap()
        target = list(range(2**64 - 1, 2**64 -1 - ARRAY_MAX_SIZE - 1, -1))
        for i in target:
            bmp.add(i)
        target = list(reversed(target))
        self.assertEqual(target, list(bmp))

    def test_bitmap_add2(self):
        bmp = self.get_sample_bitmap()
        target = list(range(ARRAY_MAX_SIZE))
        target.extend(range(2**32, 2**32 + 10))
        target.append(2**64 - 3)
        target.append(2**64 - 2)
        target.append(2**64 - 1)
        self.assertEqual(target, list(bmp))

    def test_bitmap_serialize_no_optimization(self):
        bmp = self.get_sample_bitmap()
        bio = io.BytesIO()
        written = bmp.write_to(bio, optimize=False)
        with open("tests/fixtures/serialized.bitmap", "rb") as f:
            target = f.read()
        self.assertEqual(target, bio.getvalue())
        self.assertEqual(8274, written)

    def test_bitmap_serialize_optimized(self):
        bmp = self.get_sample_bitmap()
        bio = io.BytesIO()
        written = bmp.write_to(bio)
        with open("tests/fixtures/serialized-optimized.bitmap", "rb") as f:
            target = f.read()
        self.assertEqual(target, bio.getvalue())
        self.assertEqual(74, written)

    def get_sample_bitmap(self):
        bmp = Bitmap()
        for i in range(ARRAY_MAX_SIZE):
            bmp.add(i)
        for i in range(2**32, 2**32 + 10):
            bmp.add(i)
        bmp.add(2**64 - 1)
        bmp.add(2**64 - 2)
        bmp.add(2**64 - 3)
        return bmp


if __name__ == "__main__":
    unittest.main()