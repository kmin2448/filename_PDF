import unittest

from src.core.categories import BUDGET_CATEGORIES, folder_name_for, folder_names


class FolderNameTests(unittest.TestCase):
    def test_all_registered_categories_get_numbered_folders(self):
        expected = {
            "인건비": "01. 인건비",
            "장학금": "02. 장학금",
            "교육연구프로그램개발운영비": "03. 교육연구프로그램개발운영비",
            "교육연구환경개선비": "04. 교육연구환경개선비",
            "실험실습장비및기자재구입운영비": "05. 실험실습장비및기자재구입운영비",
            "기업지원협력활동비": "07. 기업지원협력활동비",
            "성과활용확산지원비": "08. 성과활용확산지원비",
            "그 밖의사업운영경비": "09. 그 밖의사업운영경비",
        }
        for category, folder in expected.items():
            with self.subTest(category=category):
                self.assertEqual(folder_name_for(category), folder)
        self.assertEqual(folder_names(), list(expected.values()))
        self.assertEqual(len(BUDGET_CATEGORIES), len(expected))

    def test_whitespace_and_linebreaks_are_ignored(self):
        self.assertEqual(folder_name_for("실험실습장비 및\n기자재구입운영비"), "05. 실험실습장비및기자재구입운영비")
        self.assertEqual(folder_name_for("그밖의사업운영경비"), "09. 그 밖의사업운영경비")
        self.assertEqual(folder_name_for("  인건비  "), "01. 인건비")

    def test_partial_match(self):
        self.assertEqual(folder_name_for("학생인건비"), "01. 인건비")
        self.assertEqual(folder_name_for("교육연구환경개선비(비품)"), "04. 교육연구환경개선비")

    def test_already_numbered_input_is_kept(self):
        self.assertEqual(folder_name_for("01. 인건비"), "01. 인건비")
        self.assertEqual(folder_name_for("02.장학금"), "02. 장학금")

    def test_unknown_category_falls_back_to_sanitized_name(self):
        self.assertEqual(folder_name_for("기타경비"), "기타경비")
        self.assertEqual(folder_name_for("기타/경비:테스트"), "기타 경비 테스트")

    def test_empty_category_raises(self):
        with self.assertRaises(ValueError):
            folder_name_for("")
        with self.assertRaises(ValueError):
            folder_name_for(None)


if __name__ == "__main__":
    unittest.main()
