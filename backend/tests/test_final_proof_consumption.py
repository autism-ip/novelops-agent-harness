"""
[INPUT]: Actual final-lock API and controlled external corruption after a verified workflow completes.
[OUTPUT]: Finalization requires current projection, Critic and deterministic verification evidence for the selected prose.
[POS]: ZEN-40 consumption regression; deterministic provider outputs are setup, not real-model quality proof.
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import copy
import json

import pytest

from app.generation import digest
from app.harness import encode
from tests.test_chapter_loop import chapter as chapter, pass_run
from tests.test_chapter_projection_boundaries import HEADERS, api_for, raw_record, readonly, transport_of

pytest_plugins = ("tests.test_creative_workflow", "tests.test_story_planning")


@pytest.mark.parametrize("fault", ["projection_hash", "report_reference", "missing_report", "missing_verifier",
                                  "verifier_false", "changed_prose", "wrong_report_type", "version_source_refs",
                                  "version_source_identity", "invalid_report_schema", "invalid_draft_schema"])
def test_final_lock_cannot_promote_a_version_with_broken_verification_evidence(chapter, fault, tmp_path):
    kernel, provider, book_id = chapter
    view = pass_run(kernel, provider, book_id)
    assert view["run"]["status"] == "completed" and view["selected"] and view["critique"]
    version = view["versions"][0]
    command = {k: version[k] for k in ("version_id", "artifact_id", "version_no")}
    command["operator"] = "synthetic-final-editor"
    transport = transport_of(kernel)
    baseline = copy.deepcopy(transport.tables)
    cv_repo, ar_repo = kernel.storage._repos["chapter_versions"], kernel.storage._repos["artifacts"]
    _, projected = raw_record(kernel, transport, "chapter_versions", "version_id", version["version_id"])
    report_id = view["critique"]["artifact_id"]
    verifier_id = view["selected"]["content"]["verification_artifact_id"]
    draft_id = view["selected"]["source_refs"][2]
    if fault == "projection_hash":
        projected["fields"][cv_repo._field_map["content_hash"]] = "changed-hash"
    elif fault == "report_reference":
        projected["fields"][cv_repo._field_map["review_report_id"]] = command["artifact_id"]
    elif fault in {"missing_report", "missing_verifier"}:
        physical_id, _ = raw_record(kernel, transport, "artifacts", "artifact_id",
                                    report_id if fault == "missing_report" else verifier_id)
        del transport.tables[ar_repo._table_id][physical_id]
    else:
        target_id = {"verifier_false": verifier_id, "changed_prose": command["artifact_id"],
                     "wrong_report_type": report_id, "version_source_refs": command["artifact_id"],
                     "version_source_identity": command["artifact_id"], "invalid_report_schema": report_id,
                     "invalid_draft_schema": draft_id}[fault]
        _, artifact = raw_record(kernel, transport, "artifacts", "artifact_id", target_id)
        payload = json.loads(artifact["fields"][ar_repo._field_map["payload_json"]])
        if fault == "verifier_false":
            payload["content"]["passed"] = False
        elif fault == "changed_prose":
            payload["content"]["prose"] += " A later unverified change."
        elif fault == "version_source_refs":
            payload["source_refs"] = payload["source_refs"][:-1]
        elif fault == "version_source_identity":
            payload["content"]["state_version"] += 1
        elif fault == "invalid_report_schema":
            payload["content"]["pacing"]["score"] = -1
        elif fault == "invalid_draft_schema":
            payload["content"]["prose"] = ""
        else:
            payload["artifact_type"] = "ChapterVerification"
        payload["content_hash"] = digest(payload["content"])
        artifact["fields"][ar_repo._field_map["payload_json"]] = encode(payload)
        if fault in {"changed_prose", "version_source_identity"}:
            projected["fields"][cv_repo._field_map["content_hash"]] = payload["content_hash"]
    before, calls, model_calls = copy.deepcopy(transport.tables), len(transport.calls), list(provider.calls)
    api = api_for(kernel)
    try:
        path = f"/api/books/{book_id}/chapters/1/final-lock"
        response = api.post(path, headers=HEADERS, json=command)
        (tmp_path / "final-proof-observation.json").write_text(json.dumps({
            "fault": fault, "status": response.status_code, "body": response.json(),
            "before": before, "after": transport.tables, "model_calls_before": model_calls,
            "model_calls_after": provider.calls}, indent=2))
        assert response.status_code == 409, response.text
        assert response.json() == {"detail": "ChapterVersion is not ready for final lock"}
        assert transport.tables == before
        readonly(transport.calls[calls:])
        assert provider.calls == model_calls
        transport.tables = copy.deepcopy(baseline)
        restored = api.post(path, headers=HEADERS, json=command)
        assert restored.status_code == 200 and restored.json()["status"] == "final"
        final_state, calls = copy.deepcopy(transport.tables), len(transport.calls)
        replay = api.post(path, headers=HEADERS, json=command)
        assert replay.status_code == 200 and replay.json() == restored.json()
        assert transport.tables == final_state
        readonly(transport.calls[calls:])
        assert kernel.artifacts.get(view["selected"]["artifact_id"]) == view["selected"]
        assert provider.calls == model_calls
    finally:
        api.close()
