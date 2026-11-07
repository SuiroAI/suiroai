"""dscraft-backed DSC-27 development profiling helper.

These require the dscraft eda backend and are skipped without it, mirroring the
lean-dependency posture elsewhere. They assert that routing numeric EDA through
dscraft preserves the exact summary numbers DSC-27 discloses (count/min/max/
mean and the exact interpolating median), and that the KLL quantile profile is
exposed alongside.
"""
import unittest

try:
    import dscraft  # noqa: F401
    from dscraft.eda import LazyEDA  # noqa: F401

    _HAVE_EDA = True
except ImportError:  # pragma: no cover
    _HAVE_EDA = False

if _HAVE_EDA:
    from suiroai.preparation.profiling import frame_profile, numeric_summary


@unittest.skipUnless(_HAVE_EDA, "dscraft eda backend not installed")
class NumericSummaryTests(unittest.TestCase):
    def test_exact_count_min_max_mean(self):
        s = numeric_summary([1, 2, 2, 4, 8])
        self.assertEqual(s["count"], 5)
        self.assertEqual(s["minimum"], 1.0)
        self.assertEqual(s["maximum"], 8.0)
        self.assertEqual(s["mean"], (1 + 2 + 2 + 4 + 8) / 5)

    def test_odd_count_median_matches_exact(self):
        self.assertEqual(numeric_summary([1, 2, 2, 4, 8])["median"], 2.0)

    def test_even_count_median_is_exact_interpolating_not_kll(self):
        # statistics.median([1,2,3,4]) == 2.5; a raw KLL sketch would report an
        # observed value (3.0). The helper must preserve the exact disclosed median.
        self.assertEqual(numeric_summary([1, 2, 3, 4])["median"], 2.5)

    def test_empty_yields_null_stats_not_fabricated_zero(self):
        s = numeric_summary([])
        self.assertEqual(s["count"], 0)
        self.assertIsNone(s["minimum"])
        self.assertIsNone(s["maximum"])
        self.assertIsNone(s["median"])
        self.assertIsNone(s["mean"])
        self.assertEqual(s["quantiles"], {})

    def test_quantile_profile_exposed(self):
        s = numeric_summary([1, 2, 2, 4, 8], quantiles=(0.25, 0.5, 0.75))
        self.assertIn("0.25", s["quantiles"])
        self.assertIn("0.75", s["quantiles"])
        # KLL extremes are exact for small data.
        self.assertEqual(s["quantiles"]["0.0"], 1.0)
        self.assertEqual(s["quantiles"]["1.0"], 8.0)


@unittest.skipUnless(_HAVE_EDA, "dscraft eda backend not installed")
class FrameProfileTests(unittest.TestCase):
    def test_row_count_null_counts_and_numeric_columns(self):
        rows = [
            {"q": 1.0, "store": "a"},
            {"q": 2.0, "store": "a"},
            {"q": None, "store": "b"},
        ]
        prof = frame_profile(rows, numeric_columns=["q"])
        self.assertEqual(prof["row_count"], 3)
        self.assertEqual(prof["null_counts"]["q"], 1)
        self.assertEqual(prof["columns"]["q"]["count"], 2)  # non-null only
        self.assertEqual(prof["columns"]["q"]["mean"], 1.5)

    def test_empty_rows(self):
        prof = frame_profile([], numeric_columns=["q"])
        self.assertEqual(prof["row_count"], 0)
        self.assertEqual(prof["columns"]["q"]["count"], 0)


if __name__ == "__main__":
    unittest.main()
