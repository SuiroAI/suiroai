"""As-of inference from saved fitted JSON and original/augmented numeric rows.

Load the persisted selected candidate and verify its feature order, training
cutoff, and forecast population before producing frozen-origin predictions.
Use the saved model without refitting or reading actual future outcomes.
"""
from datetime import date
import json

from .core import CUTOFF, Example, ModelingError, Window
from .models import load_model


def predict_november30(store, *, candidate, feature_rows, feature_fields, horizons):
    """Return frozen-origin totals; no actual outcomes or refitting accepted.

    ``horizons`` maps training-eligible namespace/product/store keys to supplier
    lead time plus review days. Its approved source/policy binding is verified by
    the parent. A daily trajectory is a separate model output, never interpolated
    by this function. An aggregate-only model cannot release restocking orders.
    """
    payload=json.loads(store.read_bytes(candidate["model_ref"]))
    if payload.get("format") != "dsc28-fitted-model-v1":
        raise ModelingError("as-of forecast requires a persisted fitted modeling candidate")
    if payload["candidate_id"] != candidate["candidate_id"]:
        raise ModelingError("as-of inference selected a different candidate")
    if list(feature_fields)!=payload.get("feature_names"):
        raise ModelingError("inference changed frozen ordered feature names")
    if payload.get("source_refs") and candidate["feature_set_ref"] not in payload["source_refs"]:
        raise ModelingError("inference changed frozen feature set reference")
    state=payload["state"]
    if (state["training_target_end_max"] > CUTOFF.isoformat()
            or state["training_information_end_max"] > CUTOFF.isoformat()):
        raise ModelingError("frozen model was fitted with reserved outcomes")
    model=load_model(state)
    rows={}
    for row in feature_rows:
        key=(row["source_namespace"],row["Product_ID"],row["Store_ID"])
        if (row["origin"] != CUTOFF.isoformat() or key in rows
                or row.get("latest_information_available_date", "9999-12-31") > CUTOFF.isoformat()):
            raise ModelingError("as-of features need unique November30 rows and availability")
        rows[key]=row
    if set(rows)!=set(horizons) or not rows:
        raise ModelingError("as-of forecast population differs from frozen development eligibility")
    predictions=[]
    for key in sorted(horizons):
        window=Window(key,CUTOFF,horizons[key])
        if window.end > date(2025,12,31):
            raise ModelingError("protection horizon cannot be fully scored in reserved December")
        # Actual is a typed placeholder for the model protocol and never read.
        example=Example(window,tuple(rows[key][f] for f in feature_fields),0)
        predictions.append((window,model.predict(example)))
    return tuple(predictions)
