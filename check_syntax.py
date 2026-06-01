"""Quick syntax check for all project files"""
import py_compile
import os

base = os.path.dirname(__file__)

files = [
    'study_bot/config.py',
    'study_bot/data/preset.py',
    'study_bot/data/prompts.py',
    'study_bot/database/schema.py',
    'study_bot/database/models.py',
    'study_bot/database/ops.py',
    'study_bot/services/analyzer.py',
    'study_bot/services/score_predictor.py',
    'study_bot/services/test_generator.py',
    'study_bot/services/photo_solver.py',
    'study_bot/services/policy_monitor.py',
    'study_bot/services/error_tracker.py',
    'study_bot/services/plan_generator.py',
    'study_bot/services/scheduler.py',
    'study_bot/handlers/commands.py',
    'study_bot/main.py',
]

errs = 0
for f in files:
    path = os.path.join(base, f)
    try:
        py_compile.compile(path, doraise=True)
        print(f'OK: {f}')
    except py_compile.PyCompileError as e:
        print(f'FAIL: {f} - {e}')
        errs += 1

print(f'\nTotal: {len(files)}, Errors: {errs}')

# Clean up pycache
import shutil
for root, dirs, files_list in os.walk(base):
    if '__pycache__' in dirs:
        shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
