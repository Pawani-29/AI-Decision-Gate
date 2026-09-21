from app import create_app


def test_home_page_loads():
    app = create_app()
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"final payment decision is always yours" in response.data
