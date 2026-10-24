def test_user_repository_import_and_annotations():
    from app.modules.user.repository import UserRepository

    assert UserRepository.permissions_by_ids.__annotations__["ids"] == "list[int]"
    assert UserRepository.replace_overrides.__annotations__["overrides"] == "list[tuple[int, bool]]"
