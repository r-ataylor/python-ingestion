import logging, logging.config
import csv
from StringIO import StringIO
from github import Github
from glob import glob

from config import GITHUB_TOKEN

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)-7s | %(asctime)s | %(name)-8s | %(message)s',
            },
        'raw': {
            'format': '%(message)s',
            },
        },
    'handlers': {
        'file_handler': {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'filename': "validate_csvs.log",
            'mode': 'w',
            },
        'stream_handler': {
            'class': 'logging.StreamHandler',
            'level': 'ERROR',
            'formatter': 'raw',
            'stream': 'ext://sys.stdout',
            },
        },
    'loggers': {
        '': {
            'level': 'INFO',
            'handlers': ['file_handler', 'stream_handler', ],
            'propagate': False,
            },
        },
    })

repository = [
    o for o 
    in Github(GITHUB_TOKEN).get_user().get_orgs() 
    if o.login=='ooi-integration'
    ][0].get_repo('ingestion-csvs')

log = logging.getLogger('Main')

def get_csvs(repo, filepath, csv_files={}):
    for item in repo.get_dir_contents(filepath):
        if item.type == "dir":
            csv_files = get_csvs(repo, item.path)
        elif item.path.endswith(".csv"):
            csv_files[item.path] = StringIO(item.decoded_content)
            log.info("Found CSV file: %s" % item.path)
    return csv_files

def commented(row):
    ''' Check to see if the row is commented out. Any field that starts with # indictes 
        a comment.'''
    return bool([v for v in row.itervalues() if v.startswith("#")])

def file_mask_has_files(row):
    ''' Check to see if any files are found that match the file mask. '''
    return bool(len(glob(row["filename_mask"])))

def file_mask_has_deployment_number(row):
    ''' Check to see if a deployment number can be parsed from the file mask. '''
    try:
        deployment_number = int([
            n for n 
            in row['filename_mask'].split("/") 
            if len(n)==6 and n[0] in ('D', 'R', 'X')
            ][0][1:])
    except:
        return False
    return True

def ingest_queue_matches_data_source(row):
    ''' Check to see if the ingestion route matches the data source specification. '''
    return row['uframe_route'].split("_")[-1] == row['data_source']

log.info("Verifying CSVs stored at %s" % repository.html_url)

csv_files = get_csvs(repository, ".")

for f in csv_files:
    reader = csv.DictReader(csv_files[f])
    log.info("")
    log.info("Validating CSV file: %s" % f) 
    parameters = [r for r in reader if not commented(r)]
    for i, row in enumerate(parameters):
        try:
            if not file_mask_has_files(row):
                log.warning(
                    "%s: No files found for %s (%s)." % (i + 2, row["filename_mask"], f))
            if not file_mask_has_deployment_number(row):
                log.warning(
                    "%s: Can't parse Deployment Number from %s (%s)." % (i + 2, row["filename_mask"], f))
            if not ingest_queue_matches_data_source(row):
                log.warning(
                    "%s: UFrame Route doesn't match Data Source: %s, %s" % (
                        i + 2, row['uframe_route'], row['data_source']))
        except Exception:
            log.exception(f)