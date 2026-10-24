import copy
import json
from pathlib import Path
import unittest
from tool import analyze, report_html

FIXTURE = Path(__file__).resolve().parents[1]/'examples/demo.json'


class TimingTests(unittest.TestCase):
    def data(self):
        return json.loads(FIXTURE.read_text())

    def test_known_metrics(self):
        s = analyze(self.data())['summary']
        self.assertEqual(s['median_response_gap_ms'], 500)
        self.assertEqual(s['p95_response_gap_ms'], 1500)
        self.assertEqual(s['over_budget_turns'], 1)
        self.assertEqual(s['cross_speaker_overlap_ms'], 200)
        self.assertEqual(s['internal_dead_air_ms'], 3000)

    def test_exact_budget_not_violation(self):
        self.assertEqual(analyze(self.data(), 1500)['summary']['over_budget_turns'], 0)

    def test_overlap_not_slow_response(self):
        row = analyze(self.data())['turns'][-1]
        self.assertEqual(row['response_gap_ms'], -200)
        self.assertFalse(row['over_budget'])
        self.assertEqual(row['overlap_label'], 'intended')

    def test_boolean_and_reversed_intervals_rejected(self):
        for value in [True, -1, 1800, '0']:
            data = self.data()
            data['turns'][0]['user']['start_ms'] = value
            with self.assertRaises(ValueError):
                analyze(data)

    def test_duplicate_ids_rejected(self):
        data = self.data()
        data['turns'][1]['id'] = data['turns'][0]['id']
        with self.assertRaises(ValueError):
            analyze(data)

    def test_same_speaker_overlap_rejected(self):
        data = self.data()
        data['turns'][1]['user']['start_ms'] = 1000
        with self.assertRaises(ValueError):
            analyze(data)

    def test_no_initial_or_trailing_silence_invented(self):
        data = self.data()
        for t in data['turns']:
            for role in ('user','assistant'):
                t[role]['start_ms'] += 50000
                t[role]['end_ms'] += 50000
        self.assertEqual(analyze(data)['summary']['internal_dead_air_ms'], 3000)

    def test_html_escapes_input(self):
        data = self.data()
        data['turns'][0]['id'] = '<script>alert(1)</script>'
        output = report_html(analyze(data))
        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;', output)

    def test_empty_input_rejected(self):
        with self.assertRaises(ValueError):
            analyze({'turns':[]})


if __name__ == '__main__':
    unittest.main()
