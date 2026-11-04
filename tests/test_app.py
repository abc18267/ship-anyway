"""Browser regressions. Run: python -m unittest discover -s tests -v
Requires Python Playwright and its Chromium browser. Uses a temporary localhost
server and an isolated browser profile; both close when the test run ends.
"""
import functools
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import unittest

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
KEY = 'shipanyway.v1'
DAY = 86400000


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844})
        self.context.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        self.page = self.context.new_page()
        self.page.set_default_timeout(5000)
        self.page.clock.install()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.url)

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], 'Browser JavaScript errors')

    def state(self):
        return self.page.evaluate('(key) => JSON.parse(localStorage.getItem(key))', KEY)

    def seed(self, state):
        self.page.evaluate('([key,state]) => localStorage.setItem(key, JSON.stringify(state))', [KEY, state])
        self.page.reload()

    def start(self, title='Open the proposal'):
        self.page.locator('#t-title').fill(title)
        self.page.get_by_role('button', name='Start 2 minutes', exact=True).click()
        expect(self.page.get_by_text(title, exact=True)).to_be_visible()

    def save_place(self, note='Add the price to paragraph two'):
        self.page.locator('[data-action="stop"]').click()
        self.page.locator('#save-step').fill(note)
        self.page.locator('[data-action="saveplace"]').click()

    def upload(self, data):
        self.page.locator('#restore-file').set_input_files({
            'name': 'backup.json', 'mimeType': 'application/json',
            'buffer': json.dumps(data).encode(),
        })

    def test_quick_start_save_reload_resume_and_complete(self):
        expect(self.page.locator('#start-options')).not_to_have_attribute('open', '')
        self.start()
        original = self.state()
        self.assertTrue(original['active']['quick'])
        self.assertEqual(original['active']['ends']-original['active']['startedAt'], 120000)
        self.save_place()
        saved = self.state()
        self.assertIsNone(saved['active'])
        self.assertEqual(saved['tasks'][0]['started'], original['tasks'][0]['started'])
        self.assertEqual(saved['tasks'][0]['nextStep'], 'Add the price to paragraph two')
        self.page.reload()
        self.page.get_by_role('button', name='Resume for 2 minutes').click()
        expect(self.page.locator('.next-step')).to_contain_text('Add the price')
        self.assertEqual(self.state()['tasks'][0]['started'], original['tasks'][0]['started'])
        self.page.get_by_role('button', name='Task is done', exact=True).click()
        self.assertIsNotNone(self.state()['tasks'][0]['shipped'])

    def test_two_minutes_expire_gently_and_continue(self):
        self.start()
        self.page.clock.fast_forward(121000)
        expect(self.page.get_by_text('You started. That counts.', exact=False)).to_be_visible()
        expect(self.page.locator('#clock')).to_have_text('00:00')
        self.page.get_by_role('button', name='Continue for 25 minutes').click()
        self.assertFalse(self.state()['active']['quick'])
        expect(self.page.get_by_text('Done means', exact=True)).to_be_visible()
        expect(self.page.locator('#clock')).to_have_text('25:00')

    def test_stuck_step_persists_on_existing_task(self):
        self.start()
        task_id = self.state()['tasks'][0]['id']
        self.page.get_by_role('button', name='I’m stuck', exact=True).click()
        self.assertIsNotNone(self.state()['active']['pausedAt'])
        self.page.get_by_role('button', name='It feels too big').click()
        self.page.locator('#sp-step').fill('Write the first sentence')
        self.page.get_by_role('button', name='Start this step · 2 minutes').click()
        after = self.state()
        self.assertEqual(len(after['tasks']), 1)
        self.assertEqual(after['active']['taskId'], task_id)
        self.assertEqual(after['tasks'][0]['nextStep'], 'Write the first sentence')
        self.assertTrue(after['events'][0]['recovered'])
        self.page.reload()
        expect(self.page.locator('.next-step')).to_contain_text('Write the first sentence')

    def test_stuck_without_task_starts_immediately(self):
        self.page.get_by_role('button', name='I’m stuck', exact=True).click()
        self.page.get_by_role('button', name='It feels too big').click()
        self.page.locator('#sp-step').fill('Open the file')
        self.page.get_by_role('button', name='Start this step · 2 minutes').click()
        self.assertEqual(self.state()['tasks'][0]['title'], 'Open the file')
        self.assertTrue(self.state()['active']['quick'])

    def test_polishing_and_overwhelmed_routes(self):
        self.start()
        self.page.get_by_role('button', name='I’m stuck', exact=True).click()
        self.page.get_by_role('button', name='I’m overwhelmed').click()
        self.page.locator('[data-action="saveplace"]').click()
        expect(self.page.get_by_role('button', name='Resume for 2 minutes')).to_be_visible()
        self.page.get_by_role('button', name='Resume for 2 minutes').click()
        self.page.get_by_role('button', name='I’m stuck', exact=True).click()
        self.page.get_by_role('button', name='I keep polishing').click()
        expect(self.page.get_by_role('dialog')).to_contain_text('Done means')
        self.page.get_by_role('button', name='Yes — task is done').click()
        self.assertTrue(self.state()['tasks'][0]['shipped'])

    def test_dialog_cancel_resumes_and_keyboard_stays_inside(self):
        self.start()
        original = self.state()['active']['ends']
        self.page.get_by_role('button', name='I’m stuck', exact=True).click()
        self.page.clock.fast_forward(30000)
        self.page.get_by_role('button', name='Back', exact=True).focus()
        self.page.keyboard.press('Tab')
        expect(self.page.get_by_role('button', name='It feels too big')).to_be_focused()
        self.page.keyboard.press('Shift+Tab')
        expect(self.page.get_by_role('button', name='Back', exact=True)).to_be_focused()
        self.page.keyboard.press('Escape')
        expect(self.page.get_by_role('dialog')).not_to_be_visible()
        self.assertIsNone(self.state()['active']['pausedAt'])
        self.assertGreaterEqual(self.state()['active']['ends'], original+30000)
        self.assertEqual(self.state()['events'], [])

    def test_paused_timer_stays_paused_after_dialog(self):
        self.start()
        self.page.get_by_role('button', name='Pause timer', exact=True).click()
        before = self.state()['active']['pausedAt']
        self.page.get_by_role('button', name='I’m stuck', exact=True).click()
        self.page.keyboard.press('Escape')
        self.assertEqual(self.state()['active']['pausedAt'], before)

    def test_legacy_data_and_older_unfinished_tasks_survive(self):
        self.start()
        state = self.state()
        state['tasks'][0]['created'] -= 250*DAY
        state['tasks'][0]['started'] = None
        state['tasks'][0]['planned'] = '2020-01-01'
        state['active'] = None
        state['updated'] -= 10*DAY
        self.seed(state)
        expect(self.page.get_by_text('Welcome back. Pick one small thing.')).to_be_visible()
        self.start('Another small action')
        self.assertEqual(len(self.state()['tasks']), 2)
        self.assertEqual(self.state()['tasks'][0]['title'], 'Open the proposal')
        self.save_place()
        self.page.get_by_text('Other saved tasks (1)', exact=True).click()
        expect(self.page.get_by_text('Open the proposal', exact=True)).to_be_visible()

    def test_backup_download_restore_and_invalid_backup(self):
        self.start('Original task')
        self.save_place('Original note')
        self.page.get_by_role('link', name='Setup', exact=True).click()
        with self.page.expect_download() as download:
            self.page.get_by_role('button', name='Download backup', exact=True).click()
        backup = json.loads(Path(download.value.path()).read_text())
        self.assertEqual(backup['tasks'][0]['nextStep'], 'Original note')
        self.page.get_by_role('link', name='Now', exact=True).click()
        self.start('Extra task')
        self.save_place()
        self.upload({'v': 7})
        expect(self.page.get_by_role('dialog')).to_contain_text('Backup not restored')
        self.assertEqual(len(self.state()['tasks']), 2)
        self.page.keyboard.press('Escape')
        self.upload(backup)
        expect(self.page.get_by_role('dialog')).to_contain_text('1 tasks')
        with self.page.expect_download():
            self.page.get_by_role('button', name='Download current data & restore').click()
        self.assertEqual(len(self.state()['tasks']), 1)
        self.assertEqual(self.state()['tasks'][0]['title'], 'Original task')
        self.page.reload()
        expect(self.page.get_by_text('Next: Original note')).to_be_visible()

    def test_restore_running_session_is_paused(self):
        self.start()
        backup = self.state()
        self.save_place()
        self.upload(backup)
        with self.page.expect_download():
            self.page.get_by_role('button', name='Download current data & restore').click()
        self.assertIsNotNone(self.state()['active']['pausedAt'])
        expect(self.page.locator('#clock')).to_have_text('paused')

    def test_restore_storage_failure_does_not_replace_current_work(self):
        self.start('Original')
        backup = self.state()
        self.save_place()
        self.start('Keep this task')
        self.save_place()
        self.upload(backup)
        self.page.evaluate("() => { Storage.prototype.setItem = function() { throw new DOMException('Full', 'QuotaExceededError'); }; }")
        with self.page.expect_download():
            self.page.get_by_role('button', name='Download current data & restore').click()
        expect(self.page.locator('#toast')).to_contain_text('Your current work has not changed')
        self.assertEqual(len(self.state()['tasks']), 2)
        self.page.keyboard.press('Escape')
        expect(self.page.get_by_text('Keep this task', exact=True)).to_be_visible()

    def test_legacy_active_session_loads_without_resetting_timer(self):
        self.start()
        backup = self.state()
        del backup['active']['quick']
        self.seed(backup)
        expect(self.page.get_by_text('Done means', exact=True)).to_be_visible()
        self.assertEqual(self.state()['active']['ends'], backup['active']['ends'])

    def test_optional_movement_timer_runs_across_views(self):
        self.page.locator('#t-title').fill('Write draft')
        self.page.get_by_text('More options', exact=True).click()
        self.page.locator('#t-ex').check()
        self.page.get_by_role('button', name='Start a focus session').click()
        self.assertEqual(self.state()['active']['phase'], 'exercise')
        self.page.get_by_role('link', name='Setup', exact=True).click()
        self.page.clock.fast_forward(1201000)
        self.assertEqual(self.state()['active']['phase'], 'work')
        self.page.get_by_role('link', name='Now', exact=True).click()
        expect(self.page.get_by_text('Done means', exact=True)).to_be_visible()

    def test_storage_failure_keeps_work_exportable(self):
        self.page.evaluate("() => { Storage.prototype.setItem = function() { throw new DOMException('Full', 'QuotaExceededError'); }; }")
        self.start()
        expect(self.page.get_by_role('alert')).to_contain_text('could not be saved')
        with self.page.expect_download() as download:
            self.page.get_by_role('button', name='Download current work', exact=True).click()
        backup = json.loads(Path(download.value.path()).read_text())
        self.assertEqual(backup['tasks'][0]['title'], 'Open the proposal')
        self.assertIsNotNone(backup['active'])

    def test_corrupt_saved_data_is_not_overwritten(self):
        self.page.evaluate('(key) => localStorage.setItem(key, "{broken")', KEY)
        self.page.reload()
        expect(self.page.get_by_role('alert')).to_contain_text('kept untouched')
        self.start()
        self.assertEqual(self.page.evaluate('(key) => localStorage.getItem(key)', KEY), '{broken')
        with self.page.expect_download() as download:
            self.page.get_by_role('button', name='Download original saved data').click()
        self.assertEqual(Path(download.value.path()).read_text(), '{broken')

    def test_checkins_optional_later_skip_and_problem_copy(self):
        self.start()
        state = self.state()
        state['tasks'][0]['shipped'] = int(time.time()*1000)-2*DAY
        state['active'] = None
        self.seed(state)
        expect(self.page.get_by_role('button', name='Start 2 minutes')).to_be_visible()
        self.page.get_by_text('Optional check-ins (1)', exact=True).click()
        self.page.get_by_role('button', name='Too soon to tell').click()
        self.assertGreater(self.state()['tasks'][0]['checkAfter'], int(time.time()*1000))
        state = self.state()
        state['tasks'][0]['checkAfter'] = 0
        self.seed(state)
        self.page.get_by_text('Optional check-ins (1)', exact=True).click()
        self.page.get_by_role('button', name='Real problem', exact=True).click()
        expect(self.page.locator('#toast')).to_contain_text('repair or a request for help')
        self.assertEqual(self.state()['tasks'][0]['outcome'], 'problem')

    def test_focus_timer_navigation_revision_and_pause_voice(self):
        self.page.locator('#t-title').fill('Send invoice')
        self.page.get_by_text('More options', exact=True).click()
        self.page.locator('[data-cap="15"]').click()
        self.page.get_by_role('button', name='Start a focus session').click()
        self.page.evaluate("window.shipAnyway.command('pause')")
        paused = self.state()['active']['pausedAt']
        self.page.evaluate("window.shipAnyway.command('pause')")
        self.assertEqual(self.state()['active']['pausedAt'], paused)
        self.page.evaluate("window.shipAnyway.command('resume')")
        self.assertIsNone(self.state()['active']['pausedAt'])
        self.page.get_by_role('link', name='Week', exact=True).click()
        self.page.clock.fast_forward(901000)
        self.assertIn('Time to check in', self.page.title())
        self.page.get_by_role('link', name='Now', exact=True).click()
        self.page.get_by_role('button', name='One specific fix · 5 minutes').click()
        self.page.locator('#revision-step').fill('Check the total')
        self.page.get_by_role('button', name='Start the final 5 minutes').click()
        expect(self.page.locator('#clock')).to_have_text('05:00')
        expect(self.page.locator('.next-step')).to_contain_text('Check the total')
        self.page.clock.fast_forward(301000)
        expect(self.page.locator('[data-action="morepass"]')).to_have_count(0)
        self.assertEqual(self.state()['active']['passes'], 2)

    def test_mobile_and_desktop_layout_and_voice_notice(self):
        for width in [320, 390, 1280]:
            self.page.set_viewport_size({'width': width, 'height': 844})
            self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        self.page.get_by_role('link', name='Setup', exact=True).click()
        expect(self.page.get_by_text('There is no account sync.', exact=False)).to_be_visible()
        self.page.get_by_role('button', name='Voice commands & privacy').click()
        expect(self.page.get_by_role('dialog')).to_contain_text('may send audio')
        self.page.keyboard.press('Escape')
        self.page.get_by_role('button', name='Talk', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_contain_text('speech recognition provider')
        self.page.get_by_role('button', name='Use buttons').click()

    def test_set_aside_is_reversible(self):
        self.start()
        self.save_place()
        self.page.get_by_role('button', name='Set aside Open the proposal').click()
        self.page.get_by_text('Set aside (1)', exact=True).click()
        self.page.get_by_role('button', name='Bring back').click()
        expect(self.page.get_by_role('button', name='Resume for 2 minutes')).to_be_visible()


if __name__ == '__main__':
    unittest.main()
