"""Deterministic orchestrator and workflow worker; knowledge answers use source text."""
import re
from retrieval import tokens

TOPICS = {
    'portal': {'keywords': {'portal','login','password','locked','account'}, 'owner': 'it-portal'},
    'records': {'keywords': {'enrollment','letter','transcript','certificate','record','course'}, 'owner': 'student-records'},
    'devices': {'keywords': {'wifi','wireless','network','device','laptop','connection'}, 'owner': 'it-devices'},
    'staff': {'keywords': {'leave','payroll','payslip','employment'}, 'owner': 'staff-hr'},
    'library': {'keywords': {'library','loan','book','renew','catalog'}, 'owner': 'library-desk'},
    'facilities': {'keywords': {'room','building','fault','equipment','classroom','heating'}, 'owner': 'facilities-desk'},
    'finance': {'keywords': {'tuition','invoice','payment','fee','finance'}, 'owner': 'finance-desk'},
}


def analyze(request, requester_role, sources, directory, stamp):
    # A weak one-word match can rank in search without supporting a useful reply.
    # Keep the dominant evidence cluster when building the grounded response.
    if sources:
        sources = [source for source in sources if source['score'] >= sources[0]['score'] * .28]
    terms = set(tokens(request))
    topics = [key for key, value in TOPICS.items() if terms & value['keywords']]
    # "Course portal" is an IT service, rather than a separate enrollment issue.
    if 'portal' in topics and 'records' in topics and not terms & {'enrollment','letter','transcript','certificate','record'}:
        topics.remove('records')
    question = bool(re.match(r'^(how|what|where|when|can|do|does|is|are)\b', request.strip(), re.I))
    trouble = bool(terms & {'locked','fail','failed','failing','incorrect','broken','lost','cannot','correction','approve','approval','restored','issue','problem','fault','missed'})
    restricted = 'staff' in topics and requester_role == 'student'
    path = 'knowledge' if question and not trouble and sources and not restricted else 'workflow'
    assignee, department, missing = None, 'Human Triage', []
    if path == 'knowledge':
        status = 'answered'
        reason = 'A procedural question matched visible knowledge. The knowledge worker returned cited source sentences.'
    elif restricted:
        sources = []
        status = 'triage'
        reason = 'This student request concerns a staff procedure. A coordinator must clarify eligibility.'
        missing = ['Confirm the service and requester eligibility.']
    elif len(topics) != 1:
        status = 'triage'
        reason = 'Several services are involved; a coordinator must identify the primary service.' if topics else 'No supported service owner was identified; a coordinator needs more detail.'
        missing = ['Which service should be handled first?'] if topics else ['Which service is affected and what outcome do you need?']
    elif topics == ['staff'] and 'leave' in terms and not re.search(r'\d', request):
        status = 'triage'
        reason = 'A staff leave request needs dates before it can be assigned.'
        missing = ['Provide the start date, end date, and leave type.']
    else:
        assignee = next((p for p in directory if p['id'] == TOPICS[topics[0]]['owner'] and requester_role in p['roles']), None)
        if assignee:
            status, department = 'assigned', assignee['department']
            reason = f"The workflow worker matched {topics[0]} service terms and validated {assignee['name']} in {department}."
        else:
            status = 'triage'
            reason = 'The proposed owner is unavailable or ineligible. Human triage must assign the request.'
    answer = '\n\n'.join(f"{source['excerpt']} [{source['id']}]" for source in sources[:2]) if sources else 'No visible knowledge supplied a supported answer. A service coordinator will review this request.'
    trace = [
        {'stage': 'Orchestrator', 'detail': f"Selected the {path} path for this {requester_role} request.", 'at': stamp},
        {'stage': 'Knowledge retrieval', 'detail': 'Applied role visibility before indexed BM25 ranking. Retrieved ' + (', '.join(s['id'] for s in sources) or 'no visible matching source') + '.', 'at': stamp},
        {'stage': 'Knowledge answer' if path == 'knowledge' else 'Workflow analysis', 'detail': reason, 'at': stamp},
        {'stage': 'Directory validation', 'detail': f"Confirmed {assignee['name']} belongs to {department} and can receive {requester_role} requests." if assignee else ('No assignment required for this knowledge answer.' if path == 'knowledge' else 'Held in the coordinator inbox without an automatic owner.'), 'at': stamp},
    ]
    return {'path': path, 'status': status, 'department': department if path == 'workflow' else sources[0]['department'], 'assignee_id': assignee['id'] if assignee else None, 'assignee': assignee['name'] if assignee else None, 'topics': topics, 'citations': sources, 'answer': answer, 'routing_reason': reason, 'missing_information': missing, 'trace': trace}
