import json
from unittest import mock

from django.test import RequestFactory, TestCase
from django.urls import reverse

from paying_for_college.documents import SchoolDocument
from paying_for_college.models import School
from paying_for_college.models.search import SchoolSearch
from paying_for_college.views import school_autocomplete


# Tests API endpoint: /api/search-schools.json?q=Kansas
class SchoolSearchTest(TestCase):
    fixtures = ["test_fixture.json", "test_school.json"]

    @mock.patch.object(SchoolDocument, "search")
    def test_school_autocomplete(self, mock_search):
        # Mock what Opensearch would return in response to a query.
        mock_search.return_value.query.return_value.execute.return_value = [
            SchoolDocument.from_opensearch(
                {
                    "_source": SchoolDocument().prepare(
                        School.objects.get(pk=155317)
                    )
                }
            )
        ]

        autocomplete = reverse("paying_for_college:disclosures:school_search")
        request = RequestFactory().get(f"{autocomplete}?q=Kansas")
        response = school_autocomplete(request)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            json.loads(response.content),
            [
                {
                    "schoolname": "University of Kansas",
                    "id": 155317,
                    "city": "Lawrence",
                    "nicknames": "Jayhawks",
                    "state": "KS",
                    "zip5": "",
                    "url": reverse(
                        "paying_for_college:disclosures:school-json",
                        args=(155317,),
                    ),
                }
            ],
        )

    @mock.patch.object(SchoolDocument, "search")
    def test_autocomplete_school_id(self, mock_search):
        school_id = "155317"
        school = School.objects.get(pk=155317)
        school.save()
        mock_return = mock.Mock()
        mock_return.search_term = school_id
        mock_return.school_id = school.school_id
        mock_queryset = mock.Mock()
        mock_queryset.__iter__ = mock.Mock(return_value=iter([mock_return]))
        mock_queryset.count.return_value = 1
        response = self.client.get(
            reverse("paying_for_college:disclosures:school_search"),
            {"q": school_id},
        )
        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(155317, mock_return.school_id)

    @mock.patch.object(SchoolDocument, "search")
    def test_autocomplete_nickname(self, mock_search):
        nickname = "Jayhawks"
        school = School.objects.get(pk=155317)
        school.save()
        mock_return = mock.Mock()
        mock_return.search_term = nickname
        mock_return.nicknames = nickname
        mock_queryset = mock.Mock()
        mock_queryset.__iter__ = mock.Mock(return_value=iter([mock_return]))
        mock_queryset.count.return_value = 1
        response = self.client.get(
            reverse("paying_for_college:disclosures:school_search"),
            {"q": nickname},
        )
        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("Jayhawks" in mock_return.nicknames)

    @mock.patch.object(SchoolDocument, "search")
    def test_autocomplete_city(self, mock_search):
        city = "Lawrence"
        school = School.objects.get(pk=155317)
        school.save()
        mock_return = mock.Mock()
        mock_return.search_term = city
        mock_return.city = school.city
        mock_queryset = mock.Mock()
        mock_queryset.__iter__ = mock.Mock(return_value=iter([mock_return]))
        mock_queryset.count.return_value = 1
        response = self.client.get(
            reverse("paying_for_college:disclosures:school_search"),
            {"q": city},
        )
        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("Lawrence" in mock_return.city)

    @mock.patch.object(SchoolDocument, "search")
    def test_autocomplete_state(self, mock_search):
        state = "KS"
        school = School.objects.get(pk=155317)
        school.save()
        mock_return = mock.Mock()
        mock_return.search_term = state
        mock_return.state = state
        mock_queryset = mock.Mock()
        mock_queryset.__iter__ = mock.Mock(return_value=iter([mock_return]))
        mock_queryset.count.return_value = 1
        response = self.client.get(
            reverse("paying_for_college:disclosures:school_search"),
            {"q": state},
        )
        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(response.status_code, 200)
        self.assertTrue("KS" in mock_return.state)

    @mock.patch.object(SchoolDocument, "search")
    def test_autocomplete_no_term(self, mock_search):
        term = ""
        mock_return = mock.Mock()
        mock_return.search_term = term
        mock_queryset = mock.Mock()
        mock_queryset.__iter__ = mock.Mock(return_value=iter([mock_return]))
        mock_queryset.count.return_value = 1
        response = self.client.get(
            reverse("paying_for_college:disclosures:school_search"),
            {"q": term},
        )
        self.assertEqual(mock_search.call_count, 0)
        self.assertEqual(response.status_code, 200)

    @mock.patch.object(SchoolSearch, "autocomplete")
    def test_autocomplete_blank_term(self, mock_autocomplete):
        url = "{}?q=".format(
            reverse("paying_for_college:disclosures:school_search")
        )
        response = school_autocomplete(RequestFactory().get(url))
        self.assertEqual(json.loads(response.content), [])
        self.assertEqual(mock_autocomplete.call_count, 0)
        self.assertEqual(response.status_code, 200)

    @mock.patch.object(SchoolDocument, "search")
    def test_autocomplete_closed(self, mock_search):
        school = School.objects.get(pk=987654)
        school.save()
        mock_return = mock.Mock()
        mock_return.search_term = "closed"
        mock_return.text = school.primary_alias
        mock_return.school_id = school.school_id
        mock_return.city = school.city
        mock_return.state = school.state
        mock_return.zip5 = school.zip5
        mock_queryset = mock.Mock()
        mock_queryset.__iter__ = mock.Mock(return_value=iter([mock_return]))
        mock_queryset.count.return_value = 0
        url = "{}?q=closed".format(
            reverse("paying_for_college:disclosures:school_search")
        )
        response = school_autocomplete(RequestFactory().get(url))
        self.assertEqual(json.loads(response.content), [])
        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(b"closed" in response.content)
        self.assertFalse(b"987654" in response.content)
        self.assertFalse(b"Closed Town" in response.content)
