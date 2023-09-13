#!/usr/bin/python3

import sys

import osc.conf
import osc.core

from osclib.core import get_request_list_with_history
from lxml import etree as ET
from urllib.error import HTTPError, URLError

import ReviewBot


class FactorySourceChecker(ReviewBot.ReviewBot):
    """ This review bot is obsolete since the introduction of better
    alternatives like origin-manager. But it's kept because other bots like
    TagChecker (check_tags_in_request) still call this bot as part of their
    implementation.

    This review bot was used in the past to check if the sources of a submission
    are either in Factory or a request for Factory with the same sources exist.
    If the latter a request is only accepted if the Factory request is reviewed
    positive."""

    def __init__(self, *args, **kwargs):
        ReviewBot.ReviewBot.__init__(self, *args, **kwargs)
        self.factory = ["openSUSE:Factory", "openSUSE.org:openSUSE:Factory"]
        self.review_messages = {'accepted': 'ok', 'declined': 'the package needs to be accepted in Factory first'}
        self.history_limit = 5

    def check_source_submission(self, src_project, src_package, src_rev, target_project, target_package):
        super(FactorySourceChecker, self).check_source_submission(
            src_project, src_package, src_rev, target_project, target_package)
        src_srcinfo = self.get_sourceinfo(src_project, src_package, src_rev)
        if src_srcinfo is None:
            # source package does not exist?
            # handle here to avoid crashing on the next line
            self.logger.info("Could not get source info for %s/%s@%s" % (src_project, src_package, src_rev))
            return False
        projects = self._package_get_upstream_projects(target_package)
        if projects is None:
            self.logger.error("no upstream project found for {}, can't check".format(target_package))
            return False

        self.review_messages['declined'] = 'the package needs to be accepted in {} first'.format(' or '.join(projects))
        for project in projects:
            self.logger.info("Checking in project %s" % project)
            good = self._check_matching_srcmd5(project, target_package, src_srcinfo.verifymd5, self.history_limit)
            if good:
                self.logger.info("{} is in {}".format(target_package, project))
                return good

            good = self._check_requests(project, target_package, src_srcinfo.verifymd5)
            if good:
                self.logger.info("{} already reviewed for {}".format(target_package, project))

        if not good:
            self.logger.info('{} failed source submission check'.format(target_package))

        return good

    def _check_requests(self, project, package, rev):
        self.logger.debug("checking requests")
        prjprefix = ''
        apiurl = self.apiurl
        sr = 'sr'
        try:
            if self.config.project_namespace_api_map:
                for prefix, url, srprefix in self.config.project_namespace_api_map:
                    if project.startswith(prefix):
                        apiurl = url
                        prjprefix = prefix
                        project = project[len(prefix):]
                        sr = srprefix
                        break
            requests = get_request_list_with_history(apiurl, project, package, None, ['new', 'review'], 'submit')
        except (HTTPError, URLError):
            self.logger.error("caught exception while checking %s/%s", project, package)
            return None

        def srref(reqid):
            return '#'.join((sr, reqid))

        for req in requests:
            for a in req.actions:
                si = self.get_sourceinfo(prjprefix + a.src_project, a.src_package, a.src_rev)
                self.logger.debug("rq %s: %s/%s@%s" % (req.reqid, prjprefix +
                                  a.src_project, a.src_package, si.verifymd5))
                if si.verifymd5 != rev:
                    self.logger.info("%s to %s has different sources", srref(req.reqid), project)
                    continue

                if req.state.name == 'new':
                    self.logger.info("%s ok", srref(req.reqid))
                    return True
                if req.state.name != 'review':
                    self.logger.error("%s in state %s not expected", srref(req.reqid), req.state.name)
                    return None

                self.logger.debug("%s still in review", srref(req.reqid))
                if not req.reviews:
                    self.logger.error("%s in state review but no reviews?", srref(req.reqid))
                    return False
                for r in req.reviews:
                    if r.state == 'new':
                        if r.by_project and r.by_project.startswith('openSUSE:Factory:Staging:'):
                            self.logger.info("%s review by %s ok", srref(req.reqid), r.by_project)
                            continue

                        if r.by_user == 'repo-checker':
                            self.logger.info('%s review by %s ok', srref(req.reqid), r.by_user)
                            continue

                    if r.state == 'accepted':
                        continue
                    if r.by_user:
                        self.logger.info("%s waiting for review by %s", srref(req.reqid), r.by_user)
                    elif r.by_group:
                        self.logger.info("%s waiting for review by %s", srref(req.reqid), r.by_group)
                    elif r.by_project:
                        if r.by_package:
                            self.logger.info("%s waiting for review by %s/%s",
                                             srref(req.reqid), r.by_project, r.by_package)
                        else:
                            self.logger.info("%s waiting for review by %s", srref(req.reqid), r.by_project)
                    return None
                return True

        return False

    def _package_get_upstream_projects(self, package):
        """ return list of projects where the specified package is supposed to come
        from. Either by lookup table or self.factory """
        projects = []
        for prj in self.factory:
            r = self.lookup.get(prj, package)
            if r:
                projects.append(r)

        if not projects:
            projects = self.factory

        return projects


class TagChecker(ReviewBot.ReviewBot):
    """ simple bot that checks that a submit request has corrrect tags specified
    """

    def __init__(self, *args, **kwargs):
        super(TagChecker, self).__init__(*args, **kwargs)
        self.factory = ["openSUSE:Factory", "openSUSE.org:openSUSE:Factory"]
        self.review_messages['declined'] = """
(This is a script, so report bugs)

The project you submitted to requires a bug tracker ID marked in the
.changes file. OBS supports several patterns, see
$ osc api /issue_trackers

See also https://en.opensuse.org/openSUSE:Packaging_Patches_guidelines#Current_set_of_abbreviations

Note that not all of the tags listed there are necessarily supported
by OBS on which this bot relies.
"""
        self.request_default_return = True

    def isNewPackage(self, tgt_project, tgt_package):
        try:
            self.logger.debug("package_meta %s %s/%s" % (self.apiurl, tgt_project, tgt_package))
            osc.core.show_package_meta(self.apiurl, tgt_project, tgt_package)
        except (HTTPError, URLError):
            return True
        return False

    def checkTagInRequest(self, req, a):
        u = osc.core.makeurl(self.apiurl,
                             ['source', a.src_project, a.src_package],
                             {'cmd': 'diff',
                              'onlyissues': '1',
                              'view': 'xml',
                              'opackage': a.tgt_package,
                              'oproject': a.tgt_project,
                              'expand': '1',
                              'rev': a.src_rev})
        try:
            f = osc.core.http_POST(u)
        except (HTTPError, URLError):
            if self.isNewPackage(a.tgt_project, a.tgt_package):
                self.review_messages['accepted'] = 'New package'
                return True

            self.logger.debug('error loading diff, assume transient error')
            return None

        xml = ET.parse(f)
        issues = len(xml.findall('./issues/issue'))
        deleted = len(xml.findall('./issues/issue[@state="deleted"]'))
        if issues == 0:
            self.logger.debug("reject: diff contains no tags")
            return False
        if deleted > 0:
            self.review_messages['declined'] = '{} issue reference(s) deleted'.format(deleted)
            return False
        return True

    def checkTagNotRequired(self, req, a):
        # if there is no diff, no tag is required
        diff = osc.core.request_diff(self.apiurl, req.reqid)
        if not diff:
            return True

        # 1) A tag is not required only if the package is
        # already in Factory with the same revision,
        # and the package is being introduced, not updated
        # 2) A new package must have an issue tag
        factory_checker = FactorySourceChecker(apiurl=self.apiurl,
                                               dryrun=self.dryrun,
                                               logger=self.logger,
                                               user=self.review_user,
                                               group=self.review_group)
        factory_checker.factory = self.factory
        factory_ok = factory_checker.check_source_submission(a.src_project, a.src_package, a.src_rev,
                                                             a.tgt_project, a.tgt_package)
        return factory_ok

    def checkTagNotRequiredOrInRequest(self, req, a):
        tags = self.checkTagInRequest(req, a)
        if tags is True:
            return True

        return self.checkTagNotRequired(req, a)

    def check_action_submit(self, req, a):
        return self.checkTagNotRequiredOrInRequest(req, a)

    def check_action_maintenance_incident(self, req, a):
        return self.checkTagInRequest(req, a)

    def check_action_maintenance_release(self, req, a):
        return self.checkTagInRequest(req, a)


class CommandLineInterface(ReviewBot.CommandLineInterface):

    def __init__(self, *args, **kwargs):
        ReviewBot.CommandLineInterface.__init__(self, args, kwargs)
        self.clazz = TagChecker

    def get_optparser(self):
        parser = ReviewBot.CommandLineInterface.get_optparser(self)
        parser.add_option("--factory", metavar="project", help="the openSUSE Factory project")

        return parser

    def setup_checker(self):
        bot = ReviewBot.CommandLineInterface.setup_checker(self)

        if self.options.factory:
            bot.factory = [self.options.factory]

        return bot


if __name__ == "__main__":
    app = CommandLineInterface()
    sys.exit(app.main())
