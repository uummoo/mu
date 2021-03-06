import unittest

from mu.utils import interpolations


class AbstractTest(unittest.TestCase):
    def test_construction(self):
        self.assertRaises(TypeError, interpolations.Interpolation)

        class Test(interpolations.Interpolation):
            pass

        self.assertRaises(TypeError, Test)


class InterpolationsTest(unittest.TestCase):
    def test_linear(self):
        linear0 = interpolations.Linear()
        linear1 = interpolations.Linear()
        self.assertEqual(hash(linear0), hash(linear1))
        inter0 = linear0(0, 10, 6)
        inter1 = linear0(0, 5, 6)
        self.assertEqual(inter0, (0, 2, 4, 6, 8, 10))
        self.assertEqual(inter1, (0, 1, 2, 3, 4, 5))

    def test_logarithmic(self):
        logarithmic0 = interpolations.Logarithmic()
        logarithmic1 = interpolations.Logarithmic()
        self.assertEqual(hash(logarithmic0), hash(logarithmic1))
        inter0 = logarithmic0(0, 10, 6)
        self.assertEqual(
            inter0,
            (
                0,
                0.00015848931924611142,
                0.0025118864315095794,
                0.03981071705534969,
                0.630957344480193,
                10,
            ),
        )

    def test_proportional(self):
        prop0 = interpolations.Proportional(1)
        prop1 = interpolations.Proportional(1)
        prop2 = interpolations.Proportional(0.5)
        prop3 = interpolations.Proportional(2)
        self.assertEqual(hash(prop0), hash(prop1))
        self.assertNotEqual(hash(prop0), hash(prop2))
        inter0 = prop0(0, 10, 6)
        inter1 = prop2(0, 10, 6)
        inter2 = prop3(0, 10, 6)
        self.assertEqual(inter0, (0, 2, 4, 6, 8, 10))
        self.assertEqual(
            tuple(round(n, 2) for n in inter1), (0, 2.67, 4.95, 6.95, 8.67, 10)
        )
        self.assertEqual(
            tuple(round(n, 2) for n in inter2), (0, 1.33, 2.93, 4.93, 7.33, 10)
        )


class InterpolationEventTest(unittest.TestCase):
    def test_construction(self):
        self.assertRaises(TypeError, interpolations.InterpolationEvent)
