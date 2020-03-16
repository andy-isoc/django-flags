from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpRequest, QueryDict
from django.test import TestCase
from django.utils import timezone

from flags.conditions import (
    CONDITIONS,
    DuplicateCondition,
    RequiredForCondition,
    after_date_condition,
    anonymous_condition,
    before_date_condition,
    boolean_condition,
    get_condition,
    parameter_condition,
    path_condition,
    register,
    user_condition,
)
from mock import MagicMock


class ConditionRegistryTestCase(TestCase):
    def test_register_decorator(self):
        fn = lambda conditional_value: True
        register("decorated")(fn)
        self.assertIn("decorated", CONDITIONS)
        self.assertEqual(CONDITIONS["decorated"], fn)

    def test_register_fn(self):
        fn = lambda conditional_value: True
        register("undecorated", fn=fn)
        self.assertIn("undecorated", CONDITIONS)
        self.assertEqual(CONDITIONS["undecorated"], fn)

    def test_register_dup_condition(self):
        with self.assertRaises(DuplicateCondition):
            register("boolean", fn=lambda value: value)

    def test_register_decorator_dup_condition(self):
        with self.assertRaises(DuplicateCondition):
            register("boolean")(lambda value: value)

    def test_register_required_kwargs(self):
        pass

    def test_get_condition(self):
        fn = lambda conditional_value: True
        register("gettable", fn=fn)
        self.assertEqual(get_condition("gettable"), fn)

    def test_get_condition_none(self):
        self.assertEqual(get_condition("notgettable"), None)


class BooleanConditionTestCase(TestCase):
    def test_boolean_condition_valid(self):
        self.assertTrue(boolean_condition(True))

    def test_boolean_condition_invalid(self):
        self.assertFalse(boolean_condition(False))

    def test_boolean_condition_valid_string(self):
        self.assertTrue(boolean_condition("True"))
        self.assertTrue(boolean_condition("true"))
        self.assertTrue(boolean_condition("t"))
        self.assertTrue(boolean_condition("yes"))
        self.assertTrue(boolean_condition("y"))
        self.assertTrue(boolean_condition("on"))
        self.assertTrue(boolean_condition("1"))
        self.assertTrue(boolean_condition(" true"))
        self.assertTrue(boolean_condition("true   "))

    def test_boolean_condition_invalid_string(self):
        self.assertFalse(boolean_condition("False"))
        self.assertFalse(boolean_condition("false"))
        self.assertFalse(boolean_condition("f"))
        self.assertFalse(boolean_condition("no"))
        self.assertFalse(boolean_condition("n"))
        self.assertFalse(boolean_condition("off"))
        self.assertFalse(boolean_condition("0"))


class UserConditionTestCase(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            username="testuser", email="test@user"
        )
        self.request = HttpRequest()
        self.request.user = user

    def test_user_valid(self):
        self.assertTrue(user_condition("testuser", request=self.request))

    def test_user_invalid(self):
        self.assertFalse(user_condition("nottestuser", request=self.request))

    def test_request_required(self):
        with self.assertRaises(RequiredForCondition):
            user_condition("testuser")

    def test_with_custom_user(self):
        mock_user = MagicMock()
        mock_user.get_username.return_value = "test@test.com"
        self.request.user = mock_user

        self.assertTrue(user_condition("test@test.com", request=self.request))


class AnonymousConditionTestCase(TestCase):
    def setUp(self):
        self.request = HttpRequest()

    def test_anonymous_valid(self):
        self.request.user = AnonymousUser()
        self.assertTrue(anonymous_condition(True, request=self.request))

    def test_anonymous_invalid(self):
        user = User.objects.create_user(
            username="notadminuser", email="test@user"
        )
        self.request.user = user
        self.assertFalse(anonymous_condition(True, request=self.request))

    def test_request_required(self):
        with self.assertRaises(RequiredForCondition):
            anonymous_condition(True)


class ParameterConditionTestCase(TestCase):
    def setUp(self):
        self.request = HttpRequest()

    def test_parameter_condition_valid(self):
        self.request.GET = QueryDict("my_flag=True")
        self.assertTrue(parameter_condition("my_flag", request=self.request))

        self.request.GET = QueryDict("my_flag=today")
        self.assertTrue(
            parameter_condition("my_flag=today", request=self.request)
        )

        self.request.GET = QueryDict("my_flag")
        self.assertTrue(parameter_condition("my_flag=", request=self.request))

    def test_parameter_condition_non_existent(self):
        self.request.GET = QueryDict("my_flag=True")
        self.assertFalse(
            parameter_condition("my_flag=false", request=self.request)
        )

        self.request.GET = QueryDict("my_flag=True")
        self.assertFalse(
            parameter_condition("my_flag=today", request=self.request)
        )

        self.request.GET = QueryDict("my_flag")
        self.assertFalse(parameter_condition("my_flag", request=self.request))

        self.request.GET = QueryDict("")
        self.assertFalse(
            parameter_condition("my_flag=", request=self.request)
        )

    def test_request_required(self):
        with self.assertRaises(RequiredForCondition):
            parameter_condition("my_flag")


class PathConditionTestCase(TestCase):
    def setUp(self):
        self.request = HttpRequest()

    def test_path_condition_valid_exact(self):
        self.request.path = "/my/path"
        self.assertTrue(path_condition("/my/path", request=self.request))

    def test_path_condition_valid_subpath(self):
        self.request.path = "/my/path/to/somewhere"
        self.assertTrue(path_condition("/my/path", request=self.request))

    def test_path_condition_valid_not_starting_with(self):
        self.request.path = "/subsection/my/path"
        self.assertTrue(path_condition("/my/path", request=self.request))

    def test_path_condition_invalid(self):
        self.request.path = "/your/path"
        self.assertFalse(path_condition("/my/path", request=self.request))

    def test_request_required(self):
        with self.assertRaises(RequiredForCondition):
            path_condition("/my/path")


class AfterDateConditionTestCase(TestCase):
    def setUp(self):
        # Set up some datetimes relative to now for testing
        delta = timedelta(days=1)

        self.past_datetime_tz = timezone.now() - delta
        self.past_datetime_notz = self.past_datetime_tz.replace(tzinfo=None)
        self.past_datetime_tz_str = self.past_datetime_tz.isoformat()
        self.past_datetime_notz_str = self.past_datetime_notz.isoformat()

        self.future_datetime_tz = timezone.now() + delta
        self.future_datetime_notz = self.future_datetime_tz.replace(
            tzinfo=None
        )
        self.future_datetime_tz_str = self.future_datetime_tz.isoformat()
        self.future_datetime_notz_str = self.future_datetime_notz.isoformat()

    def test_date_timeone_true(self):
        self.assertTrue(after_date_condition(self.past_datetime_tz))

    def test_date_no_timeone_true(self):
        self.assertTrue(after_date_condition(self.past_datetime_notz))

    def test_date_str_timeone_true(self):
        self.assertTrue(after_date_condition(self.past_datetime_tz_str))

    def test_date_str_no_timeone_true(self):
        self.assertTrue(after_date_condition(self.past_datetime_notz_str))

    def test_date_timeone_false(self):
        self.assertFalse(after_date_condition(self.future_datetime_tz))

    def test_date_no_timeone_false(self):
        self.assertFalse(after_date_condition(self.future_datetime_notz))

    def test_date_str_timeone_false(self):
        self.assertFalse(after_date_condition(self.future_datetime_tz_str))

    def test_date_str_no_timeone_false(self):
        self.assertFalse(after_date_condition(self.future_datetime_notz_str))

    def test_not_valid_date_str(self):
        self.assertFalse(after_date_condition("I am not a valid date"))


class BeforeDateConditionTestCase(TestCase):
    def setUp(self):
        # Set up some datetimes relative to now for testing
        delta = timedelta(days=1)

        self.past_datetime_tz = timezone.now() - delta
        self.past_datetime_notz = self.past_datetime_tz.replace(tzinfo=None)
        self.past_datetime_tz_str = self.past_datetime_tz.isoformat()
        self.past_datetime_notz_str = self.past_datetime_notz.isoformat()

        self.future_datetime_tz = timezone.now() + delta
        self.future_datetime_notz = self.future_datetime_tz.replace(
            tzinfo=None
        )
        self.future_datetime_tz_str = self.future_datetime_tz.isoformat()
        self.future_datetime_notz_str = self.future_datetime_notz.isoformat()

    def test_date_timeone_true(self):
        self.assertTrue(before_date_condition(self.future_datetime_tz))

    def test_date_no_timeone_true(self):
        self.assertTrue(before_date_condition(self.future_datetime_notz))

    def test_date_str_timeone_true(self):
        self.assertTrue(before_date_condition(self.future_datetime_tz_str))

    def test_date_str_no_timeone_true(self):
        self.assertTrue(before_date_condition(self.future_datetime_notz_str))

    def test_date_timeone_false(self):
        self.assertFalse(before_date_condition(self.past_datetime_tz))

    def test_date_no_timeone_false(self):
        self.assertFalse(before_date_condition(self.past_datetime_notz))

    def test_date_str_timeone_false(self):
        self.assertFalse(before_date_condition(self.past_datetime_tz_str))

    def test_date_str_no_timeone_false(self):
        self.assertFalse(before_date_condition(self.past_datetime_notz_str))

    def test_not_valid_date_str(self):
        self.assertFalse(before_date_condition("I am not a valid date"))
