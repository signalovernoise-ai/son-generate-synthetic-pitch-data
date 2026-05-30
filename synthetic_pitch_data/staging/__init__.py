"""Staging layer: clean and standardise raw source extracts.

This package is intentionally isolated from the generators in
`synthetic_pitch_data.company.*`. Cleaning must discover issues from the data
itself (profiling + a detector battery), never from knowledge of how the
synthetic data was produced. Do not import generator modules here.
"""
