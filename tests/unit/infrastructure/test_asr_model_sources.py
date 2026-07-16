import pytest

from memoflow.infrastructure.ai.asr_model_sources import (
    BACKENDS,
    catalog_model_id,
    default_local_dir_for_backend,
    get_source,
    hf_repo_for_backend,
    modelscope_repo_for_backend,
)


@pytest.mark.parametrize(
    ("backend", "hf_repo", "modelscope_repo", "local_dir"),
    [
        (
            "mlx_moss",
            "vanch007/mlx-MOSS-Transcribe-Diarize",
            None,
            "./models/mlx-MOSS-Transcribe-Diarize",
        ),
        (
            "moss_hf",
            "OpenMOSS-Team/MOSS-Transcribe-Diarize",
            "OpenMOSS/MOSS-Transcribe-Diarize",
            "./models/MOSS-Transcribe-Diarize",
        ),
        (
            "vibevoice",
            "microsoft/VibeVoice-ASR-HF",
            "microsoft/VibeVoice-ASR-HF",
            "./models/VibeVoice-ASR",
        ),
    ],
)
def test_backend_repo_mapping(backend, hf_repo, modelscope_repo, local_dir):
    source = get_source(backend)
    assert source.backend == backend
    assert source.hf_repo_id == hf_repo
    assert source.modelscope_repo_id == modelscope_repo
    assert source.default_local_dir == local_dir
    assert hf_repo_for_backend(backend) == hf_repo
    assert modelscope_repo_for_backend(backend) == modelscope_repo
    assert default_local_dir_for_backend(backend) == local_dir
    if modelscope_repo:
        assert catalog_model_id(backend) == modelscope_repo
    else:
        assert catalog_model_id(backend) == hf_repo


def test_mlx_moss_has_no_modelscope_repo():
    assert modelscope_repo_for_backend("mlx_moss") is None


def test_get_source_rejects_unknown_backend():
    with pytest.raises(KeyError, match="未知 ASR backend"):
        get_source("unknown")


def test_backends_covers_all_sources():
    assert BACKENDS == frozenset({"mlx_moss", "moss_hf", "vibevoice"})
