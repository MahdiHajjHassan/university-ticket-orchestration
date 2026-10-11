import tempfile
import unittest
from pathlib import Path

from service import Product


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.product = Product(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def submit(self, text, role='student'):
        return self.product.action('submit', {'requester': 'Maya Reed', 'role': role, 'text': text})['ticket']

    def test_knowledge_question_has_extractive_citations_and_no_assignment(self):
        ticket = self.submit('How do I reset my course portal password?')
        self.assertEqual(ticket['path'], 'knowledge')
        self.assertEqual(ticket['status'], 'answered')
        self.assertIsNone(ticket['assignee_id'])
        self.assertEqual(ticket['citations'][0]['id'], 'KB-101')
        for source in ticket['citations']:
            self.assertIn(source['excerpt'], source['body'])
        self.assertIn('KB-101', ticket['answer'])

    def test_workflow_owner_and_resolution_survive_reload(self):
        ticket = self.submit('My course portal is locked. The reset link fails and I need access restored.')
        self.assertEqual(ticket['path'], 'workflow')
        self.assertEqual(ticket['assignee_id'], 'it-portal')
        self.assertTrue(all(s['department'] == 'IT Support' for s in ticket['citations']))
        self.assertIn('account is locked', ticket['answer'])
        updated = self.product.action('resolve', {'ticket_id': ticket['id'], 'version': ticket['version'], 'actor': 'it-portal', 'note': 'Account unlocked and requester confirmed access.'})['ticket']
        self.assertEqual(updated['status'], 'resolved')
        refreshed = Product(Path(self.tmp.name)).state()
        stored = next(t for t in refreshed['tickets'] if t['id'] == ticket['id'])
        self.assertEqual(stored['resolution']['note'], updated['resolution']['note'])
        self.assertEqual(stored['trace'][-1]['stage'], 'Resolution')

    def test_role_filter_happens_before_retrieval_and_state(self):
        self.product.action('view', {'view': 'student'})
        result = self.product.action('search', {'query': 'payroll payslip annual leave approval', 'role': 'student'})
        self.assertFalse(any(s['visibility'] == 'staff' for s in result['results']))
        self.assertFalse(any(d['visibility'] == 'staff' for d in self.product.state()['knowledge']))
        with self.assertRaises(PermissionError):
            self.product.action('search', {'query': 'payroll', 'role': 'staff'})

    def test_student_staff_procedure_is_triaged_without_restricted_citations(self):
        ticket = self.submit('I need my employment payslip corrected.')
        self.assertEqual(ticket['status'], 'triage')
        self.assertIsNone(ticket['assignee_id'])
        self.assertEqual(ticket['citations'], [])

    def test_mixed_services_need_human_triage(self):
        ticket = self.submit('My portal account is locked and I need an official enrollment letter.')
        self.assertEqual(ticket['status'], 'triage')
        self.assertGreaterEqual(len(ticket['topics']), 2)

    def test_assignment_requires_eligible_directory_member_and_resolution_owner(self):
        ticket = self.submit('I need help with a service request.')
        with self.assertRaises(PermissionError):
            self.product.action('assign', {'ticket_id': ticket['id'], 'version': ticket['version'], 'actor': 'coordinator', 'assignee_id': 'staff-hr', 'note': 'Route to staff administration.'})
        updated = self.product.action('assign', {'ticket_id': ticket['id'], 'version': ticket['version'], 'actor': 'coordinator', 'assignee_id': 'student-records', 'note': 'Clarified request concerns student records.'})['ticket']
        with self.assertRaises(PermissionError):
            self.product.action('resolve', {'ticket_id': updated['id'], 'version': updated['version'], 'actor': 'it-portal', 'note': 'This actor does not own this ticket.'})
        with self.assertRaises(RuntimeError):
            self.product.action('resolve', {'ticket_id': updated['id'], 'version': ticket['version'], 'actor': 'coordinator', 'note': 'Attempt with a stale version.'})

    def test_reindex_persists_new_knowledge_and_changes_search(self):
        self.product.action('knowledge_add', {'title': 'Bicycle storage access', 'body': 'Register your bicycle at the facilities desk. A storage access card is issued after registration.', 'visibility': 'all', 'department': 'Facilities'})
        reloaded = Product(Path(self.tmp.name))
        result = reloaded.action('search', {'query': 'bicycle storage card', 'role': 'student'})
        self.assertEqual(result['results'][0]['title'], 'Bicycle storage access')
        self.assertGreater(result['results'][0]['score'], 0)
        self.assertIn('BM25', result['method'])

    def test_student_view_cannot_perform_staff_mutations(self):
        ticket = self.submit('My course portal account is locked.')
        self.product.action('view', {'view': 'student'})
        with self.assertRaises(PermissionError):
            self.product.action('resolve', {'ticket_id': ticket['id'], 'version': ticket['version'], 'actor': 'coordinator', 'note': 'Attempt from a student view.'})


if __name__ == '__main__':
    unittest.main()
