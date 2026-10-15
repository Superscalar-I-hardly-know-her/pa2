#!/usr/bin/env python3
"""Audit replacement-policy consistency in completed Task 1 comparisons."""
import json
import re
from compare_task1 import ROOT, assert_lru, read_stats


def main():
    paths=sorted((ROOT/'results/task1').glob('**/*.log'))
    paths += sorted((ROOT/'results/task2/full').glob('*/lru.log'))
    records=[]
    for path in paths:
        text=path.read_text()
        assert_lru(text,path)
        if 'Finished CPU 0 instructions:' not in text:
            raise ValueError(f'Incomplete simulation: {path}')
        warmup=int(re.search(r'^Warmup Instructions: (\d+)',text,re.M).group(1))
        measured=int(re.search(r'^Simulation Instructions: (\d+)',text,re.M).group(1))
        smoke='smoke' in path.parts
        expected=1_000_000 if smoke else 25_000_000
        assert warmup==measured==expected,path
        if not smoke:
            read_stats(path,require_lru=True)
        records.append(dict(log=str(path.relative_to(ROOT)),warmup=warmup,measured=measured,
                            replacement='LRU at all eight levels'))
    # Confirm the same check rejects combined-policy runs, rather than merely
    # trusting directory names or matching some LRU levels in each log.
    mixed=sorted((ROOT/'results/task3').glob('*/*.log'))
    for path in mixed:
        try:
            assert_lru(path.read_text(),path)
        except ValueError:
            continue
        raise AssertionError(f'Mixed-policy run unexpectedly accepted: {path}')
    assert records and mixed
    result=dict(task1_logs_checked=len(records),task3_mixed_logs_rejected=len(mixed),records=records)
    (ROOT/'results/task1/sanity-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'{len(records)} standalone logs verified: LRU throughout, correct instruction counts, complete runs')
    print(f'{len(mixed)} Task 3 mixed-policy logs correctly rejected for standalone comparisons')


if __name__=='__main__':
    main()
