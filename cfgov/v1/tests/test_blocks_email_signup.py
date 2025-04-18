import json
from unittest import mock

from django.test import TestCase

from v1.models import BlogPage, LearnPage, NewsroomPage, SublandingPage
from v1.models.snippets import EmailSignUp
from v1.tests.wagtail_pages.helpers import publish_changes, publish_page


class TestEmailSignup(TestCase):
    def check_page_content(self, page_cls, field):
        email_signup = EmailSignUp(
            heading="Email Sign Up",
            text="Sign up for our newsletter.",
            code="TEST-GD-CODE",
        )
        email_signup.save()

        page = page_cls(slug="slug", title="title")
        publish_page(child=page)

        setattr(
            page,
            field,
            json.dumps(
                [
                    {
                        "type": "email_signup",
                        "value": email_signup.pk,
                    }
                ]
            ),
        )
        publish_changes(child=page)

        response = self.client.get("/slug/")
        self.assertContains(response, "Email Sign Up")

    def test_sublanding_page_sidebar(self):
        self.check_page_content(SublandingPage, "sidefoot")

    def test_blog_page_content(self):
        self.check_page_content(BlogPage, "content")

    def test_learn_page_content(self):
        self.check_page_content(LearnPage, "content")

    @mock.patch("cdntools.backends.AkamaiBackend.post_tags")
    def test_newsroom_page_content(self, mock_post_tags):
        self.check_page_content(NewsroomPage, "content")
