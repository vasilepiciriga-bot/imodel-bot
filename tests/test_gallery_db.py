from imodel.db import gallery as gallery_db


def test_gallery_save_and_list():
    rows = []

    def execute(sql, params=()):
        if "INSERT INTO imodel_generation_results" in sql:
            rows.append(params)
        return True

    def fetchall(sql, params=()):
        if "FROM imodel_generation_results" in sql:
            return [(1, "job1", "linkedin_premium", "v1.0", "https://x", None, False, 1.0)]
        return []

    gallery_db.save_result(execute, uid=9, job_id="job1", style_key="linkedin_premium", prompt_version="v1.0", image_url="https://x")
    items = gallery_db.list_results(fetchall, 9)
    assert items[0]["job_id"] == "job1"
