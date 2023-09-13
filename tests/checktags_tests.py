# To run this test manually, go to the parent directory and run:
# LANG=C python tests/checktags_tests.py

import os
import unittest
import logging
import httpretty
import osc
from . import OBSLocal

from urllib.parse import urlparse, parse_qs

import sys
from osclib.cache import Cache
from check_tags_in_requests import TagChecker

sys.path.append(".")

APIURL = 'http://maintenancetest.example.com'
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')

AVAILABLE_FACTORIES = ["openSUSE:Factory", "openSUSE.org:openSUSE:Factory"]


class TestTagChecker(OBSLocal.TestCase):

    def tearDown(self):
        httpretty.reset()
        httpretty.disable()

    def setUp(self):
        """
        Initialize the configuration
        """

        super().setUp()
        Cache.last_updated[APIURL] = {'__oldest': '2016-12-18T11:49:37Z'}
        httpretty.reset()
        httpretty.enable()

        logging.basicConfig()
        self.logger = logging.getLogger(__file__)
        self.logger.setLevel(logging.DEBUG)

        self.checker = TagChecker(apiurl=APIURL,
                                  user='maintbot',
                                  logger=self.logger)
        self.checker.override_allow = False  # Test setup cannot handle.

        self._request_data = """
                <request id="293129" creator="darix">
                  <action type="submit">
                    <source project="editors" package="nano" rev="25"/>
                    <target project="openSUSE:Factory" package="nano"/>
                  </action>
                  <state name="review" who="factory-auto" when="2015-03-25T16:24:59">
                    <comment>Please review build success</comment>
                  </state>
                  <review state="accepted" when="2015-03-25T16:24:32" who="licensedigger" by_group="legal-auto">
                    <comment></comment>
                    <history who="licensedigger" when="2015-03-25T16:30:13">
                      <description>Review got accepted</description>
                    </history>
                  </review>
                  <review state="accepted" when="2015-03-25T16:24:32" who="factory-auto" by_group="factory-auto">
                    <comment>Check script succeeded</comment>
                    <history who="factory-auto" when="2015-03-25T16:24:59">
                      <description>Review got accepted</description>
                      <comment>Check script succeeded</comment>
                    </history>
                  </review>
                  <review state="accepted" when="2015-03-25T16:24:32" who="coolo" by_group="factory-staging">
                    <comment>No need for staging, not in tested ring projects.</comment>
                    <history who="coolo" when="2015-03-25T20:47:33">
                      <description>Review got accepted</description>
                      <comment>No need for staging, not in tested ring projects.</comment>
                    </history>
                  </review>
                  <review state="new" by_user="maintbot">
                    <comment>Please review sources</comment>
                  </review>
                  <review state="accepted" when="2015-03-25T16:24:59" who="factory-repo-checker" by_user="factory-repo-checker">
                    <comment>Builds for repo editors/openSUSE_Factory</comment>
                    <history who="factory-repo-checker" when="2015-03-25T18:28:47">
                      <description>Review got accepted</description>
                      <comment>Builds for repo editors/openSUSE_Factory</comment>
                    </history>
                  </review>
                </request>
            """
        self._request_withhistory = """
                <request id="293129" creator="darix">
                  <action type="submit">
                    <source project="editors" package="nano" rev="25"/>
                    <target project="openSUSE:Factory" package="nano"/>
                  </action>
                  <state name="review" who="factory-auto" when="2015-03-25T16:24:59">
                    <comment>Please review build success</comment>
                  </state>
                  <review state="accepted" when="2015-03-25T16:24:32" who="licensedigger" by_group="legal-auto">
                    <comment></comment>
                    <history who="licensedigger" when="2015-03-25T16:30:13">
                      <description>Review got accepted</description>
                    </history>
                  </review>
                  <review state="accepted" when="2015-03-25T16:24:32" who="factory-auto" by_group="factory-auto">
                    <comment>Check script succeeded</comment>
                    <history who="factory-auto" when="2015-03-25T16:24:59">
                      <description>Review got accepted</description>
                      <comment>Check script succeeded</comment>
                    </history>
                  </review>
                  <review state="accepted" when="2015-03-25T16:24:32" who="coolo" by_group="factory-staging">
                    <comment>No need for staging, not in tested ring projects.</comment>
                    <history who="coolo" when="2015-03-25T20:47:33">
                      <description>Review got accepted</description>
                      <comment>No need for staging, not in tested ring projects.</comment>
                    </history>
                  </review>
                  <review state="new" by_user="maintbot">
                    <comment>Please review sources</comment>
                  </review>
                  <review state="accepted" when="2015-03-25T16:24:59" who="factory-repo-checker" by_user="factory-repo-checker">
                    <comment>Builds for repo editors/openSUSE_Factory</comment>
                    <history who="factory-repo-checker" when="2015-03-25T18:28:47">
                      <description>Review got accepted</description>
                      <comment>Builds for repo editors/openSUSE_Factory</comment>
                    </history>
                  </review>
                  <history who="darix" when="2015-03-25T16:24:32">
                    <description>Request created</description>
                  </history>
                  <history who="factory-auto" when="2015-03-25T16:24:59">
                    <description>Request got a new review request</description>
                    <comment>Please review sources</comment>
                  </history>
                  <history who="factory-auto" when="2015-03-25T16:24:59">
                    <description>Request got a new review request</description>
                    <comment>Please review build success</comment>
                  </history>
                </request>
            """
        self._nano_meta = """<package name="nano" project="openSUSE:Factory">
  <title>Pico Editor Clone with Enhancements</title>
  <description>GNU nano is a small and friendly text editor. It aims to emulate the
Pico text editor while also offering a few enhancements.</description>
  <devel project="editors" package="nano"/>
</package>"""

    def _run_with_data(self, accept, issues_data, factories=[]):
        # factories: the factories to check on
        httpretty.register_uri(httpretty.POST, APIURL + '/source/editors/nano', body=issues_data)
        httpretty.register_uri(httpretty.GET, APIURL + '/source/editors/nano',
                               body="""<sourceinfo package="nano" rev="25" vrev="35" srcmd5="aa7cce4956a86aee36c3f38aa37eee2b"
                               lsrcmd5="c26618f949f5869cabcd6f989fb040ca" verifymd5="fc6b5b47f112848a1eb6fb8660b7800b">
                               <filename>nano.spec</filename><linked project="openSUSE:Factory" package="nano" /></sourceinfo>""")

        for factory in factories:
            if factory not in AVAILABLE_FACTORIES:
                # We could in theory let go of this requirement, but having the
                # known factories in AVAILABLE_FACTORIES allows us to properly
                # handle 404s.
                raise Exception("Factory %s not mocked up" % factory)

            httpretty.register_uri(httpretty.GET,
                                   osc.core.makeurl(APIURL, ['source', factory, "nano", '_meta'], {}),
                                   match_querystring=True,
                                   body=self._nano_meta)
            httpretty.register_uri(httpretty.GET,
                                   osc.core.makeurl(APIURL, ['source', factory, "nano"], {'view': 'info'}),
                                   match_querystring=True,
                                   body="""<sourceinfo package="nano" rev="25" vrev="35"
                                   srcmd5="aa7cce4956a86aee36c3f38aa37eee2b" lsrcmd5="c26618f949f5869cabcd6f989fb040ca"
                                   verifymd5="fc6b5b47f112848a1eb6fb8660b7800b"><filename>nano.spec</filename>
                                   <linked project="openSUSE:Factory" package="nano" /></sourceinfo>""")

        for factory in AVAILABLE_FACTORIES:
            httpretty.register_uri(httpretty.GET,
                                   osc.core.makeurl(APIURL, ['source', factory, "00Meta", 'lookup.yml'], {}),
                                   status=404)

            if factory not in factories:
                httpretty.register_uri(httpretty.GET,
                                       osc.core.makeurl(APIURL, ['source', factory, "nano", '_meta'], {}),
                                       status=404,
                                       match_querystring=True,
                                       body="")
                httpretty.register_uri(httpretty.GET,
                                       osc.core.makeurl(APIURL, ['source', factory, "nano"], {'view': 'info'}),
                                       status=404,
                                       match_querystring=True,
                                       body="")

        httpretty.register_uri(httpretty.GET,
                               APIURL + '/request/293129',
                               body=self._request_data)
        httpretty.register_uri(httpretty.GET,
                               APIURL + "/request/293129?withhistory=1",
                               match_querystring=True,
                               body=self._request_withhistory)

        httpretty.register_uri(httpretty.GET,
                               APIURL + '/search/request',
                               body='<collection matches="0"></collection>')

        result = {'state_accepted': None}

        def change_request(result, method, uri, headers):
            query = parse_qs(urlparse(uri).query)

            if query == {'by_user': ['maintbot'], 'cmd': ['changereviewstate'], 'newstate': ['accepted']}:
                result['state_accepted'] = True
            elif query == {'by_user': ['maintbot'], 'cmd': ['changereviewstate'], 'newstate': ['declined']}:
                result['state_accepted'] = False
            return (200, headers, '<status code="ok"/>')

        httpretty.register_uri(httpretty.POST,
                               APIURL + "/request/293129",
                               body=lambda method, uri, headers: change_request(result, method, uri, headers))

        self.checker.set_request_ids(['293129'])
        self.checker.check_requests()

        self.assertEqual(result['state_accepted'], accept)

    def test_1_issue_accept(self):
        # a new package and has issues
        self._run_with_data(True, """<sourcediff key="4ecfa5c08d7765060b4fa248aab3c7e7">
  <old project="home:snwint:sle12-sp1" package="perl-Bootloader" rev="4" srcmd5="bb554c82d62186fa4c4440ba36651028" />
  <new project="SUSE:SLE-12-SP1:GA" package="perl-Bootloader" rev="23" srcmd5="231d457675a9fca041b22d84df9d4464" />
  <files />
  <issues>
    <issue state="changed" tracker="bnc" name="151877" label="boo#151877"
           url="https://bugzilla.suse.com/show_bug.cgi?id=151877" />
  </issues>
</sourcediff>""", factories=[])

    def test_3_issues_accept(self):
        # not a new package and has issues
        # changes already in Factory
        self._run_with_data(True, """<sourcediff key="4ecfa5c08d7765060b4fa248aab3c7e7">
  <old project="home:snwint:sle12-sp1" package="perl-Bootloader" rev="4" srcmd5="bb554c82d62186fa4c4440ba36651028" />
  <new project="SUSE:SLE-12-SP1:GA" package="perl-Bootloader" rev="23" srcmd5="231d457675a9fca041b22d84df9d4464" />
  <files />
  <issues>
    <issue state="changed" tracker="bnc" name="151877" label="boo#151877" url="https://bugzilla.suse.com/show_bug.cgi?id=151877" />
    <issue state="changed" tracker="fate" name="110038" label="fate#110038" url="https://fate.suse.com/110038" />
    <issue state="deleted" tracker="bnc" name="831791" label="boo#831791" url="https://bugzilla.suse.com/show_bug.cgi?id=831791" />
  </issues>
</sourcediff>""", factories=["openSUSE:Factory"])

    def test_3_issues_accept_ibs_obs(self):
        # not a new package and has issues
        # changes already in Factory
        # specified factories are both IBS (openSUSE.org:openSUSE:Factory)
        # and OBS (openSUSE:Factory)
        self._run_with_data(True, """<sourcediff key="4ecfa5c08d7765060b4fa248aab3c7e7">
  <old project="home:snwint:sle12-sp1" package="perl-Bootloader" rev="4" srcmd5="bb554c82d62186fa4c4440ba36651028" />
  <new project="SUSE:SLE-12-SP1:GA" package="perl-Bootloader" rev="23" srcmd5="231d457675a9fca041b22d84df9d4464" />
  <files />
  <issues>
    <issue state="changed" tracker="bnc" name="151877" label="boo#151877" url="https://bugzilla.suse.com/show_bug.cgi?id=151877" />
    <issue state="changed" tracker="fate" name="110038" label="fate#110038" url="https://fate.suse.com/110038" />
    <issue state="deleted" tracker="bnc" name="831791" label="boo#831791" url="https://bugzilla.suse.com/show_bug.cgi?id=831791" />
  </issues>
</sourcediff>""", factories=["openSUSE.org:openSUSE:Factory", "openSUSE:Factory"])

    def test_no_issues_decline(self):
        # a new package and has without issues
        self._run_with_data(False, """<sourcediff key="4ecfa5c08d7765060b4fa248aab3c7e7">
  <old project="home:snwint:sle12-sp1" package="perl-Bootloader" rev="4" srcmd5="bb554c82d62186fa4c4440ba36651028" />
  <new project="SUSE:SLE-12-SP1:GA" package="perl-Bootloader" rev="23" srcmd5="231d457675a9fca041b22d84df9d4464" />
  <files />
  <issues/>
</sourcediff>""", factories=[])

    def test_no_issues_tag_decline(self):
        # a new package and has without issues tag
        self._run_with_data(False, """<sourcediff key="4ecfa5c08d7765060b4fa248aab3c7e7">
  <old project="home:snwint:sle12-sp1" package="perl-Bootloader" rev="4" srcmd5="bb554c82d62186fa4c4440ba36651028" />
  <new project="SUSE:SLE-12-SP1:GA" package="perl-Bootloader" rev="23" srcmd5="231d457675a9fca041b22d84df9d4464" />
  <files />
</sourcediff>""", factories=[])

    def test_no_issues_accept(self):
        # not a new package and has without issues
        # changes already in Factory
        self._run_with_data(True, """<sourcediff key="4ecfa5c08d7765060b4fa248aab3c7e7">
  <old project="home:snwint:sle12-sp1" package="perl-Bootloader" rev="4" srcmd5="bb554c82d62186fa4c4440ba36651028" />
  <new project="SUSE:SLE-12-SP1:GA" package="perl-Bootloader" rev="23" srcmd5="231d457675a9fca041b22d84df9d4464" />
  <files />
  <issues/>
</sourcediff>""", factories=["openSUSE:Factory"])

    def test_no_issues_tag_accept(self):
        # not a new package and has without issues tag
        # changes already in Factory
        self._run_with_data(True, """<sourcediff key="4ecfa5c08d7765060b4fa248aab3c7e7">
  <old project="home:snwint:sle12-sp1" package="perl-Bootloader" rev="4" srcmd5="bb554c82d62186fa4c4440ba36651028" />
  <new project="SUSE:SLE-12-SP1:GA" package="perl-Bootloader" rev="23" srcmd5="231d457675a9fca041b22d84df9d4464" />
  <files />
</sourcediff>""", factories=["openSUSE:Factory"])

    def test_no_issues_tag_accept_ibs_linked(self):
        # not a new package and has without issues tag
        # changes already in Factory
        # specified factory is the linked one from IBS
        self._run_with_data(True, """<sourcediff key="4ecfa5c08d7765060b4fa248aab3c7e7">
  <old project="home:snwint:sle12-sp1" package="perl-Bootloader" rev="4" srcmd5="bb554c82d62186fa4c4440ba36651028" />
  <new project="SUSE:SLE-12-SP1:GA" package="perl-Bootloader" rev="23" srcmd5="231d457675a9fca041b22d84df9d4464" />
  <files />
</sourcediff>""", factories=["openSUSE.org:openSUSE:Factory"])


if __name__ == '__main__':
    unittest.main()
