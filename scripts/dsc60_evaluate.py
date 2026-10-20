"""Reproduce development metrics and freeze a conservative DSC-60 recording candidate.

Purpose: deterministic, local diagnosis of https://linear.app/gr3enarr0w/issue/DSC-60.
Never opens December outcome files or calls the production producer/API. pandas and
numpy are optional development tools, not application runtime dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

FILES = {
    'Sales_transactions_2022_2025.csv': '520fa470ccb7ff5c7d0d8b34d157d15c05c948f7c785e48397ac676bf6cd7707',
    'ordering_policy.csv': '333614c3d0be51c2fe694b482effb2caf93d1e6b2124b14a48a5c45995fae2a6',
    'inbound_deliveries.csv': '1af4a67eb95dff218ae5fdf10446d4a1f4887022bd75c5f598babdb29904ae5a',
    'inventory_position.csv': '3836aaba4dec70b6ee3ce56529ab03353cbaa801d111f52b6bb7433f7924aef9',
}
KEYS = ['Product_ID', 'Store_ID']
BASELINE = 'recent_13_weeks'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forecasts(daily, idx, cutoff, horizon):
    """Reimplement the inspected producer formula; training is always <= origin."""
    hist = daily.loc[:cutoff]
    means = {n: hist.tail(n).mean().fillna(0).to_numpy() for n in [28, 91, 182, 364]}
    recent, year = hist.tail(91), hist.tail(364)
    total = year.sum().sum()
    product = year.sum().groupby(level=0).sum() / total
    store = year.sum().groupby(level=1).sum() / total
    pooled = np.array([product[p] * store[s] for p, s in idx]) * recent.sum().sum() / len(recent)
    blended = .5 * means[364] + .5 * pooled
    older = hist[hist.index.year < cutoff.year]
    monthly = older.sum(axis=1).groupby(older.index.month).mean()
    factors = monthly / monthly.mean()
    future = pd.date_range(cutoff + pd.Timedelta(days=1), periods=int(horizon))
    seasonal = blended * np.mean([factors.get(d.month, 1) for d in future]) / np.mean([factors.get(d.month, 1) for d in recent.index])
    return {'recent_13_weeks': means[91] * horizon, 'recent_4_weeks': means[28] * horizon,
            'recent_26_weeks': means[182] * horizon, 'annual_average': means[364] * horizon,
            'shared_patterns': blended * horizon, 'shared_seasonal': seasonal * horizon}


def aggregate(rows):
    frame = pd.DataFrame(rows)
    group = frame.groupby(['period', 'horizon', 'model'], sort=True)
    result = group[['ae', 'se', 'actual', 'n', 'bias']].sum().reset_index()
    result['mae'] = result.ae / result.n
    result['rmse'] = np.sqrt(result.se / result.n)
    result['wape'] = result.ae / result.actual
    result['bias_fraction'] = result.bias / result.actual
    return result


def score(actual, pred):
    if not (np.isfinite(actual).all() and np.isfinite(pred).all()):
        raise ValueError('Nonfinite metric inputs are forbidden')
    error = pred - actual
    return dict(ae=float(np.abs(error).sum()), se=float((error ** 2).sum()),
                actual=float(actual.sum()), n=len(actual), bias=float(error.sum()))


def bootstrap_gain(base, candidate):
    """Resample entire origins, retaining all paired entity errors in each block."""
    rng = np.random.default_rng(60)
    draws = rng.integers(0, len(base), size=(10000, len(base)))
    gains = 1 - candidate[draws].sum(axis=1) / base[draws].sum(axis=1)
    return {'relative_gain': float(1 - candidate.sum() / base.sum()),
            'origin_block_95_percent_interval': np.quantile(gains, [.025, .975]).tolist(),
            'resamples': 10000, 'seed': 60}


def run(source, output, producer):
    output.mkdir(parents=True, exist_ok=True)
    protocol = output / 'protocol.json'
    if not protocol.is_file():
        raise ValueError('Predeclare development/protocol.json before comparison')
    manifest = {name: {'sha256': sha(source / name), 'expected_sha256': digest} for name, digest in FILES.items()}
    if any(v['sha256'] != v['expected_sha256'] for v in manifest.values()):
        raise ValueError('Source hash does not match authoritative DSC-59 four-input evidence')
    # Original sales upload contains withheld dates: NEVER parse it. The receipt
    # records the released cutoff-only transformation; require its exact hash.
    released_sales = producer.parent / 'released' / 'input-4.csv'
    if sha(released_sales) != '48238e68f578f73efdbb8db3893cdfc55a0162f16e2e1690e5b2676eeeaaa0b8':
        raise ValueError('Unrecognized released development sales bytes')
    manifest['released/input-4.csv'] = {'sha256': sha(released_sales), 'purpose': 'cutoff-only sales parsed; original sales only hashed'}
    raw = pd.read_csv(released_sales)
    sales = raw.drop_duplicates().copy()
    sales['date'] = pd.to_datetime(sales.Order_Date, errors='raise')
    if sales.date.max() > pd.Timestamp('2025-11-30'):
        raise ValueError('Development data extends beyond permitted boundary')
    sales['status'] = sales.Order_Status.astype('string').str.strip().str.lower()
    policy = pd.read_csv(source / 'ordering_policy.csv')
    idx = pd.MultiIndex.from_frame(policy[KEYS])
    if not idx.is_unique:
        raise ValueError('Duplicate policy entity')
    dates = pd.date_range(sales.date.min(), '2025-11-30')
    first = sales.groupby(KEYS).date.min().reindex(idx)
    valid = (sales.Quantity > 0) & (sales.status != 'cancelled')

    def daily_for(mask, missing_zero=True):
        data = sales[mask].groupby(['date'] + KEYS).Quantity.sum().unstack(KEYS).reindex(index=dates, columns=idx)
        if missing_zero:
            data = data.fillna(0)
        for j, start in enumerate(first):
            data.iloc[data.index < start, j] = np.nan
        return data

    daily = daily_for(valid)
    origins = [o for o in pd.date_range('2025-06-29', '2025-11-23', freq='W-SUN')
               if not (o + pd.Timedelta(days=14) > pd.Timestamp('2025-09-30') and o < pd.Timestamp('2025-10-05'))]
    rows = []
    for origin in origins:
        for horizon in [7, 14]:
            if origin + pd.Timedelta(days=horizon) > dates.max():
                continue
            actual = daily.loc[origin + pd.Timedelta(days=1):origin + pd.Timedelta(days=horizon)].sum().to_numpy()
            for model, pred in forecasts(daily, idx, origin, horizon).items():
                rows.append(dict(origin=str(origin.date()), period='early_development' if origin.month < 10 else 'late_development',
                                 horizon=horizon, model=model, **score(actual, pred)))
    detail = pd.DataFrame(rows)
    summary = aggregate(rows)
    summary.to_csv(output / 'metrics.csv', index=False)
    detail.to_csv(output / 'origin_metrics.csv', index=False)
    # Only existing development summary is read, with producer split labels remapped honestly.
    prior = pd.read_csv(producer / 'evaluation_summary.csv')
    checks = []
    for record in summary.to_dict('records'):
        split = 'selection' if record['period'] == 'early_development' else 'holdout'
        old = prior[(prior.split == split) & (prior.horizon_days == record['horizon']) & (prior.model == record['model'])].iloc[0]
        checks.append(abs(record['mae'] - old.mae) < 1e-12)
    if not all(checks):
        raise ValueError('Producer metric reproduction failed')
    early = summary[(summary.period == 'early_development') & (summary.horizon == 7)]
    winner = early.sort_values(['mae', 'model']).iloc[0].model
    weekly = detail[detail.horizon == 7].pivot(index='origin', columns='model', values='ae')
    comparisons = {period: bootstrap_gain(weekly.loc[mask, BASELINE].to_numpy(), weekly.loc[mask, winner].to_numpy())
                   for period, mask in [('early_development', weekly.index < '2025-10-01'),
                                        ('late_development', weekly.index >= '2025-10-01'),
                                        ('all_development', np.ones(len(weekly), dtype=bool))]}
    leave_one = {}
    early_weekly = weekly[weekly.index < '2025-10-01']
    for origin in early_weekly.index:
        selected = early_weekly.drop(origin).sum().sort_values().index[0]
        leave_one[selected] = leave_one.get(selected, 0) + 1
    # All secondary sensitivities are diagnostics, never a selection objective.
    assumptions = {}
    for label, mask, zero in [
        ('main_positive_non_cancelled', valid, True),
        ('include_cancelled', sales.Quantity > 0, True),
        ('completed_shipped_only', (sales.Quantity > 0) & sales.status.isin(['completed', 'shipped']), True),
        ('exclude_returns', valid & sales.Return_Flag.astype(str).str.lower().ne('yes'), True),
        ('observed_days_only_zero_if_no_observed_history', valid, False),
    ]:
        data = daily_for(mask, zero)
        metrics = []
        for origin in origins:
            # Outcome remains main proxy to isolate training-assumption sensitivity.
            actual = daily.loc[origin + pd.Timedelta(days=1):origin + pd.Timedelta(days=7)].sum().to_numpy()
            preds = forecasts(data, idx, origin, 7)
            for model in [BASELINE, winner]:
                metrics.append(dict(period='all_development', horizon=7, model=model, **score(actual, preds[model])))
        assumptions[label] = aggregate(metrics).to_dict('records')
    lead_review = (policy.Supplier_Lead_Time_Days + policy.Review_Period_Days).to_numpy()
    secondary = []
    for origin in origins:
        # Fixed full population at each origin, only if every entity target is observable.
        if origin + pd.Timedelta(days=int(lead_review.max())) > dates.max():
            continue
        predictions = {h: forecasts(daily, idx, origin, int(h)) for h in set(lead_review)}
        actual = np.array([daily.iloc[:, j].loc[origin + pd.Timedelta(days=1):origin + pd.Timedelta(days=int(h))].sum() for j, h in enumerate(lead_review)])
        for model in [BASELINE, winner]:
            pred = np.array([predictions[h][model][j] for j, h in enumerate(lead_review)])
            secondary.append(dict(period='all_development', horizon='policy_lead_plus_review', model=model, **score(actual, pred)))
    aggregate(secondary).to_csv(output / 'ordering_horizon_diagnostic.csv', index=False)
    meaningful = all(c['relative_gain'] >= .05 and c['origin_block_95_percent_interval'][0] > 0 for c in comparisons.values())
    chosen = winner if meaningful else BASELINE
    # Freeze predictions without reading outcomes. A single first-week December target is proposed.
    cutoff = pd.Timestamp('2025-11-30')
    predictions = pd.DataFrame(idx.tolist(), columns=KEYS)
    predictions['target_start'] = '2025-12-01'
    predictions['target_end'] = '2025-12-07'
    predictions['baseline_units'] = forecasts(daily, idx, cutoff, 7)[BASELINE]
    predictions['candidate_units'] = forecasts(daily, idx, cutoff, 7)[chosen]
    predictions.to_csv(output / 'frozen_predictions.csv', index=False)
    rule = {'chosen': chosen, 'early_development_winner': winner, 'baseline': BASELINE,
            'rule': 'Retain baseline unless candidate clears 5% relative MAE gain and positive origin-block 95% lower bound in early, late and combined development.',
            'meaningful_robust_development_gain': meaningful, 'business_threshold_available': False,
            'recording_readiness': False, 'reason': 'Independent untouched-December provenance and approved gate absent; no holdout evaluated.'}
    (output / 'frozen_rule.json').write_text(json.dumps(rule, indent=2) + '\n')
    report = {'phase': 'development_only', 'source_manifest': manifest, 'producer_reproduced_all_maes': all(checks),
              'early_winner': winner, 'comparisons': comparisons, 'leave_one_early_origin_out_winners': leave_one,
              'sensitivity': assumptions, 'source_rows': len(raw), 'duplicates_removed': len(raw) - len(sales),
              'pairs': len(idx), 'zero_entity_day_fraction': float(daily.eq(0).sum().sum() / daily.notna().sum().sum()),
              'zero_weekly_target_fraction': float(np.mean([np.mean(daily.loc[o + pd.Timedelta(days=1):o + pd.Timedelta(days=7)].sum().to_numpy() == 0) for o in origins])),
              'status_rows': sales.status.value_counts().to_dict(), 'policy_coverage_days': sorted(set(map(int, lead_review))),
              'network_missing_calendar_days': len(dates.difference(pd.DatetimeIndex(sales.date.unique()))),
              'limitations': ['Observed-days-only diagnostic averages observed transaction days and falls back to zero for entities with no observations in window; it is not an alternative validated demand target.', 'Sparse recorded-order proxy, not unconstrained demand.', 'Zero-fill assumes exhaustive export after first recorded activity.', 'Status is final status, without as-known timestamps.', 'No historical stockout observations or stock snapshots.', 'Synthetic current policy used only for secondary horizon diagnostic.', 'October-November already development; no untouched December attestation.', 'Weekly origin bootstrap is descriptive; few origins, serial dependence and selection uncertainty remain.'],
              'decision': rule}
    (output / 'diagnostics.json').write_text(json.dumps(report, indent=2) + '\n')
    frozen = {'schema_version': 1, 'phase': 'development_only', 'acceptance_scope': 'illustrative single-origin development freeze; not DSC-9 final acceptance', 'cutoff': '2025-11-30', 'holdout_start': '2025-12-01',
              'holdout_end': '2025-12-07', 'source_sha256': {name: v['sha256'] for name, v in manifest.items()},
              'files': {name: sha(output / name) for name in ['protocol.json', 'frozen_rule.json', 'frozen_predictions.csv']},
              'code_sha256': sha(Path(__file__)), 'external_untouched_attestation': None, 'gate_approved': False}
    (output / 'freeze_manifest.json').write_text(json.dumps(frozen, indent=2) + '\n')
    print(json.dumps({'winner': winner, 'chosen': chosen, 'comparisons': comparisons, 'recording_ready': False}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--producer-output', type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.output, args.producer_output)
