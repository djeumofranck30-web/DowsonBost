"""Welcome to the Jungle search should paginate and merge every Algolia index."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_providers import (
    WTTJ_JOB_INDEXES,
    configured_providers,
    search_jobs_wttj,
)


def _algolia_response(hits: list[dict], nb_pages: int = 1) -> MagicMock:
    response = MagicMock()
    response.ok = True
    response.json.return_value = {"hits": hits, "nbPages": nb_pages}
    return response


def _hit(slug: str, name: str, company: str = "Acme") -> dict:
    return {
        "name": name,
        "slug": slug,
        "organization": {"name": company, "slug": company.lower()},
        "offices": [{"city": "Paris", "country_code": "FR"}],
        "summary": "Mission Python",
        "contract_type": "full_time",
    }


def test_wttj_merges_all_indexes_and_pages() -> None:
    first_index = [
        _algolia_response([_hit("job-a", "Dev A")], nb_pages=2),
        _algolia_response([_hit("job-b", "Dev B")], nb_pages=2),
    ]
    second_index = [
        _algolia_response([_hit("job-c", "Dev C")], nb_pages=1),
    ]
    third_index = [
        _algolia_response([_hit("job-a", "Dev A duplicate")], nb_pages=1),
    ]
    with patch(
        "job_providers.requests.post",
        side_effect=[*first_index, *second_index, *third_index],
    ) as mocked:
        jobs = search_jobs_wttj(
            "développeur python",
            max_pages=4,
            hits_per_page=1,
            location="Paris",
            country="France",
        )

    assert mocked.call_count == 4
    urls = [job["url"] for job in jobs]
    assert len(urls) == 3
    assert any("job-a" in url for url in urls)
    assert any("job-b" in url for url in urls)
    assert any("job-c" in url for url in urls)
    first_payload = mocked.call_args_list[0].kwargs["json"]
    assert first_payload["query"] == "développeur python"
    assert "optionalFilters" in first_payload
    assert any("offices.country_code:FR" in item for item in first_payload["optionalFilters"])


def test_wttj_comes_before_adzuna_in_all_mode() -> None:
    providers = configured_providers(
        secrets={
            "adzuna_app_id": "id",
            "adzuna_app_key": "key",
            "serpapi_api_key": "",
            "jooble_api_key": "",
            "careerjet_api_key": "",
            "apify_api_token": "",
        }
    )
    assert providers[0] == "wttj"
    assert providers[1] == "adzuna"


def test_wttj_indexes_cover_cms_and_locale_catalogs() -> None:
    assert "wk_cms_jobs_production" in WTTJ_JOB_INDEXES
    assert "wttj_jobs_production_fr" in WTTJ_JOB_INDEXES
    assert "wttj_jobs_production_en" in WTTJ_JOB_INDEXES
