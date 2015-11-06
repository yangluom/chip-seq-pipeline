#!/usr/bin/env python

import os, sys, subprocess, logging, dxpy, common, re, pprint

EPILOG = '''Notes:

Examples:

	%(prog)s
'''

DEFAULT_APPLET_PROJECT = 'E3 ChIP-seq'

def get_args():
	import argparse
	parser = argparse.ArgumentParser(
		description=__doc__, epilog=EPILOG,
		formatter_class=argparse.RawDescriptionHelpFormatter)

	parser.add_argument('infile', help="Experiment accessions", nargs='?', type=argparse.FileType('r'), default=sys.stdin)
	parser.add_argument('--debug',   help="Print debug messages", 				default=False, action='store_true')
	parser.add_argument('--project',    help="Project name or ID", 			default=dxpy.WORKSPACE_ID)
	parser.add_argument('--outf',    help="Output folder name or ID", 			default="/")
	parser.add_argument('--inf', nargs='*',    help="Folder(s) name or ID with tagAligns", 			default="/")
	parser.add_argument('--yes',   help="Run the workflows created", 			default=False, action='store_true')
	parser.add_argument('--tag',   help="String to add to the workflow name")
	parser.add_argument('--key', help="The keypair identifier from the keyfile.  Default is --key=default", default='default')
	parser.add_argument('--keyfile', default=os.path.expanduser("~/keypairs.json"), help="The keypair file.  Default is --keyfile=%s" %(os.path.expanduser("~/keypairs.json")))
	parser.add_argument('--gsize', help="Genome size string for MACS2, e.g. mm or hs", required=True)
	parser.add_argument('--csizes', help="chrom.sizes file for bedtobigbed, e.g. ENCODE Reference Files:/mm10/male.mm10.chrom.sizes", required=True)
	parser.add_argument('--idr', help="Run IDR", default=False, action='store_true')
	parser.add_argument('--idrversion', help="IDR version (relevant only if --idr is specified", default="2")
	parser.add_argument('--dryrun', help="Formulate the run command, but don't actually run", default=False, action='store_true')

	args = parser.parse_args()

	if args.debug:
		logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
	else: #use the defaulf logging level
		logging.basicConfig(format='%(levelname)s:%(message)s')

	return args

def get_control_id(experiment):
	# url = server + '/experiments/%s/' %(exp_id)
	# experiment = encoded_get(url, keypair)
	fastqs = common.encoded_get('')


	possible_controls = experiment.get('possible_controls')
	if not possible_controls or len(possible_controls) != 1:
		logging.error("Tried to find one possible control, found %s" %(possible_controls))
		return None
	return possible_controls[0].get('accession')

def resolve_project(identifier, privs='r'):
	project = dxpy.find_one_project(name=identifier, level='VIEW', name_mode='exact', return_handler=True, zero_ok=True)
	if project == None:
		try:
			project = dxpy.get_handler(identifier)
		except:
			logging.error('Could not find a unique project with name or id %s' %(identifier))
			raise ValueError(identifier)
	logging.debug('Project %s access level is %s' %(project.name, project.describe()['level']))
	if privs == 'w' and project.describe()['level'] == 'VIEW':
		logging.error('Output project %s is read-only' %(identifier))
		raise ValueError(identifier)
	return project

def get_ta(experiment, repn, default_project, ta_folders):
	exp_id = experiment['accession']
	possible_files = []
	for base_folder in ta_folders:
		if ':' in base_folder:
			project_name, path = base_folder.split(':')
			project = resolve_project(project_name)
			project = project.get_id()
			project_name += ":"
		else:
			project = default_project
			project_name = ""
			path = base_folder
		if not path.startswith('/'):
			path = '/' + path
		print project, project_name, path
		for dxfile in dxpy.find_data_objects(classname='file', state='closed', folder=path, describe=True, recurse=True, project=project):
			desc = dxfile.get('describe')
			if exp_id in desc.get('folder') and '/bams' in desc.get('folder') and desc.get('name').endswith(('tagAlign', 'tagAlign.gz')):
				possible_files.append(desc)
	print "%s %i possible files" %(exp_id, len(possible_files))
	folders = [f.get('folder') for f in possible_files]
	rep_folder = [folder for folder in folders if folder.endswith('rep%d' %(repn))]
	if len(rep_folder) != 1:
		logging.error("Could not find folder rep%n" %(repn))
		return None
	rep_files = [f for f in possible_files if f.get('folder') == rep_folder]

	if len(rep_files) != 1:
		logging.warning("Tried to find one rep%n ta, found %d" %(repn, len(rep_files)))
	if len(rep_files) > 0:
		if len(rep_files) > 1:
			logging.warning("Using first one found")
		rep = rep_files[0].get('project') + ':' + rep_files[0].get('folder') + '/' + rep_files[0].get('name')
	else:
		rep = None

	return rep


	# if len(folders) > 2:
	# 	logging.warning("Found %n folders, using first two found" %(len(folders)))
	# 	rep1_folder = folders[0]
	# 	rep2_folder = folders[1]

	# rep1_files = [f for f in possible_files if 'rep1' in f.get('folder')]
	# rep2_files = [f for f in possible_files if 'rep2' in f.get('folder')]

	# if len(rep1_files) != 1:
	# 	print "Tried to find one rep1 ta, found %d" %(len(rep1_files))
	# if len(rep1_files) > 0:
	# 	if len(rep1_files) > 1:
	# 		print "Using first one found"
	# 	rep1 = rep1_files[0].get('project') + ':' + rep1_files[0].get('folder') + '/' + rep1_files[0].get('name')
	# else:
	# 	rep1 = None

	# if len(rep2_files) != 1:
	# 	print "Tried to find one rep2 ta, found %d" %(len(rep2_files))
	# if len(rep2_files) > 0:
	# 	if len(rep2_files) > 1:
	# 		print "Using first one found"
	# 	rep2 = rep2_files[0].get('project') + ':' + rep2_files[0].get('folder') + '/' + rep2_files[0].get('name')
	# else:
	# 	rep2 = None
	
	# return rep1, rep2

def get_repns(exp_id, ta_folders):
	for base_folder in ta_folders:
		if ':' in base_folder:
			project_name, path = base_folder.split(':')
			project = resolve_project(project_name)
			project = project.get_id()
			project_name += ":"
		else:
			project = default_project
			project_name = ""
			path = base_folder
		if not path.startswith('/'):
			path = '/' + path
		print project, project_name, path
		for dxfile in dxpy.find_data_objects(classname='file', state='closed', folder=path, describe=True, recurse=True, project=project):
			desc = dxfile.get('describe')
			if exp_id in desc.get('folder') and '/bams' in desc.get('folder') and desc.get('name').endswith(('tagAlign', 'tagAlign.gz')):
				possible_files.append(desc)
	print "%s %i possible files" %(exp_id, len(possible_files))
	folders = [f.get('folder') for f in possible_files]
	print "%s folders %s" %(exp_id, folders)


def get_exp_tas(experiment, server, keypair, default_project, ta_folders):
	exp_id = experiment['accession']
	repns = get_repns(exp_id, ta_folders)

	rep1_ta = get_tas(experiment, repns[0], default_project, ta_folders)
	rep2_ta = get_tas(experiment, repns[1], default_project, ta_folders)
	
	return (rep1_ta,repns[0]), (rep2_ta,repns[1])

def get_ctl_tas(experiment, server, keypair, default_project, ta_folders):
	exp_id = experiment['accession']

	rep1, rep2 = get_tas(exp_id, default_project, ta_folders)
	if rep1 and rep2:
		return rep1,rep2
	elif rep1:
		return rep1,rep1
	elif rep2:
		return rep2,rep2
	else: #both are None - just pass it on and let the calling code deal with it
		return rep1,rep2

def get_encffs(s):
	return re.findall('ENCFF[0-9]{3}[A-Z]{3}',s)

def get_ta_from_accessions(accessions, default_project, ta_folders):
	possible_files = []
	for base_folder in ta_folders:
		if ':' in base_folder:
			project_name, path = base_folder.split(':')
			project = resolve_project(project_name)
			project_id = project.get_id()
			project_name += ":"
		else:
			project_id = default_project
			project_name = ""
			path = base_folder
		if not path.startswith('/'):
			path = '/' + path
		if not path.endswith('/'):
			path += '/'
		logging.debug("Looking for TA's in %s %s %s" %(project_id, project_name, path))
		for dxfile in dxpy.find_data_objects(
			classname='file',
			state='closed',
			folder=path + 'bams/',
			project=project_id,
			describe=True,
			recurse=True,
		):
			desc = dxfile.get('describe')
			if desc.get('name').endswith(('tagAlign', 'tagAlign.gz')):
				possible_files.append(desc)
		matched_files = [f for f in possible_files if all([acc in f['name'] for acc in accessions])]
		if not matched_files:
			logging.error('Could not find tagAlign with accessions %s' %(accessions))
			return None
		elif len(matched_files) > 1:
			logging.error('Found multiple tagAligns that matched accessions %s' %(accessions))
			logging.error('Matched files %s' %([(f['folder'],f['name']) for f in matched_files]))
			return None
		else:
			return matched_files[0]

def get_tas(experiment, server, keypair, default_project, ta_folders):
	# tas = {
	# 	'rep1_ta': {
	# 		'file_id': "",
	# 		'project_id': "",
	# 		'folder': "",
	# 		'name': "",
	# 		'paired_end': False,
	# 		'control_path': "",
	# 		'enc_repn': 0
	#.for each ta_folder get list of TA's in /ta_folder/bams/ENCSR...
	#.from this list infer repns from the paths ../bams/ENCSR.../repn*
	#.from this list infer the ENCFF's for the fastqs that were used
	#for each repn go to the experiment and find all the fastqs for that rep
	#if there are different fastq's in the experiment, or different reps, warn
	#for each fastq found in the TA filename, find its controlled_by
	#if any have controlled_by, all must have controlled_by else error
	#	gather the list of controlled by and find a TA (anywhere in ta_folders) with those ENCFF's, else error
	#else get possible_controls and try to match the repn, else pick one (rememeber it)
	#	gather the list of fastqs in the possible_controls and find (one) TA with those ENCFF's, else error
	exp_id = experiment['accession']
	possible_files = []
	for base_folder in ta_folders:
		if ':' in base_folder:
			project_name, path = base_folder.split(':')
			project = resolve_project(project_name)
			project_id = project.get_id()
			project_name += ":"
		else:
			project_id = default_project
			project_name = ""
			path = base_folder
		if not path.startswith('/'):
			path = '/' + path
		if not path.endswith('/'):
			path += '/'
		logging.debug("Looking for TA's in %s %s %s" %(project_id, project_name, path))
		for dxfile in dxpy.find_data_objects(
			classname='file',
			state='closed',
			folder=path + 'bams/%s/' %(exp_id),
			project=project_id,
			describe=True,
			recurse=True,
		):
			desc = dxfile.get('describe')
			if desc.get('name').endswith(('tagAlign', 'tagAlign.gz')):
				possible_files.append(desc)
	logging.debug('Found %s possible files' %(len(possible_files)))
	logging.debug('%s' %([f.get('name') for f in possible_files]))
	repns = []
	for f in possible_files:
		m = re.search('/rep(\d+)$',f['folder'])
		if m:
			repns.append(int(m.group(1)))
		else:
			logging.error("Cannot parse rep number from %s" %(f['folder']))
			return None
	logging.debug('Discovered repns %s' %(repns))
	if len(repns) != 2:
		logging.error("Required to have exactly 2 reps for %s" %(exp_id))
		return None

	tas = {}
	for i,repn in enumerate(repns):
		encode_files = [common.encoded_get(server+'/files/%s/' %(f), keypair) for f in get_encffs(possible_files[i].get('name'))]
		controlled_by = [f.get('controlled_by') for f in encode_files]
		if controlled_by:
			controlled_by_accessions = list(set([uri.split('/')[2] for uris in controlled_by for uri in uris]))
			controlled_by_ta = get_ta_from_accessions(controlled_by_accessions, default_project, ta_folders)
			if controlled_by_ta:
				controlled_by_ta_name = controlled_by_ta.get('name')
				controlled_by_ta_id = controlled_by_ta.get('id')
			else:
				logging.error("Could not find controlled_by_ta")
				controlled_by_ta_name = None
				controlled_by_ta_id = None
		else:
			controlled_by_accessions = None
			controlled_by_ta_name = None
			controlled_by_ta_id = None
		#if encode repns are 1,2 then let the pipline input rep numbers (1 or 2) be the same.
		#Otherwise the mapping is arbitrary, but at least do it with smaller rep number first.
		if repn == min(repns):
			ta_index = 1
		else:
			ta_index = 2
		tas.update(
			{'rep%d_ta' %(ta_index): {
				'file_id': possible_files[i].get('id'),
				'project_id': possible_files[i].get('project'),
				'folder': possible_files[i].get('folder'),
				'file_name': possible_files[i].get('name'),
				'enc_fqs': get_encffs(possible_files[i].get('name')),
				'controlled_by': controlled_by_accessions,
				'controlled_by_name': controlled_by_ta_name,
				'control_id': controlled_by_ta_id,
				'file_id': possible_files[i].get('id'),
				'project_id': possible_files[i].get('project'),
				'folder': possible_files[i].get('folder'),
				'enc_repn': repn
				}
			}
		)

	return tas

	#for each biorepn
	#	look for one TA in /ta_folder/bams/ENCSR.../repn else error
	#	get the list of controlled_by fastq's for all fastqs in that rep
	#	look for one TA in /ta_folder anywhere with (all) those fastqs in its name
	#	


	#	find exactly one tagAlign file anywhere in ta_folders that has each ENCFF in the filename (write a function for that) else error
	#	find the list of fastqs in controlled_by.
	#	If not empty
	#		find exactly one tagAlign anywhere in ta_folders with those ENCFFs.
	#	If empty
	#		Repeat the process above for each ENCSR in possible controls
	#
	#if none, error.  if more than one, error
	#each fastq in the rep should have the same controlled_by (or none)
	#for each rep

	#get the repn's from the experiment and the fastqs for each rep
	#for each repn look for the TA's in /ta_folder/bams/ENCSRxyzabc/repn
	#check to make sure there is exactly one TA with each fastq in its name (form ENCFF.....-ENCFF.....-ENCFF....*)
	#if not error
	#for each fastq, check to see if it has controlled_by.  If any do, all must, else error.
	#	if controlled-by,
	# 		check that all fastqs in each biorep have same controlled_by else error
	#		

	#ta_folders assumed to have the structure /ta_folder/bams/ENCSRxyzabc/repn/*.tagAlign or tagAlign.gz
	#can only get folders in DNAnexus from files, so find all the ta paths in each /ta_folder/bams/ENCSRxyzabc/
	#from that list of files, infer the repn's from the file paths
	#for each repn, get the fastq's for that experiment's reps
	#if all the fastqs for the rep have controlled_by then figure out the control experiment accession and control_repn and find the path to that control
	#if none of the fastqs for the rep have controlled_by then get possible_controls and try to match the repn in the control, if no match, pick one
	#if there are multiple possible controls, pick one by heuristic (target starts with Control)
	#print that list of files to look through those file's tafor each folder in ta_folders look for ta_folder/bams/exp_id/repn
	#find the 


def main():
	args = get_args()
	authid, authpw, server = common.processkey(args.key, args.keyfile)
	keypair = (authid,authpw)

	for exp_id in args.infile:
		if exp_id.startswith('#'):
			continue
		exp_id = exp_id.rstrip()
		print "Experiment %s" %(exp_id)
		url = server + '/experiments/%s/' %(exp_id)
		experiment = common.encoded_get(url, keypair)
		if experiment.get('target'):
			url = server + experiment.get('target')
			target = common.encoded_get(url, keypair)
		else:
			logging.error('Experiment has no target ... skipping')
			continue

		print "%s %s %s" %(experiment['accession'], target.get('investigated_as'), experiment.get('description'))
		# ctl_id = get_control_id(experiment)
		# if ctl_id:
		# 	print "Control %s" %(ctl_id)
		# else:
		# 	print "Found no control ... skipping %s" %(exp_id)
		# 	continue
		# (rep1_ta,rep1_pe), (rep2_ta,rep2_pe) = get_exp_tas(experiment, server, keypair, args.project, args.inf)
		# (ctl1_ta,ctl1_pe), (ctl2_ta,ctl2_pe) = get_ctl_tas(experiment, server, keypair, args.project, args.inf)

		tas = get_tas(experiment, server, keypair, args.project, args.inf)
		if not tas:
			logging.error('Failed to resolve all tagaligns for %s' %(experiment['accession']))
			continue

		pprint.pprint(tas)
		# sys.exit()
		#continue

		skip_flag = False
		for key,value in tas.iteritems():
			if not value:
				logging.error('Missing %s ... skipping' %(key))
				skip_flag = True
		if skip_flag:
			continue

		workflow_name = '%s Peaks' %(exp_id)
		if args.tag:
			workflow_name += ' %s' %(args.tag)
		outf = args.outf

		if not outf.startswith('/') and outf != '/':
			outf = '/'+outf
		if not outf.endswith('/') and outf != '/':
			outf += '/'
		outf += '%s/peaks/' %(exp_id)
		workflow_spinner = '~/chip-seq-pipeline/dnanexus/tf_workflow.py'
		run_command = \
			'%s --name "%s" --outf "%s" --nomap --yes ' %(workflow_spinner, workflow_name, outf) + \
			'--rep1pe false --rep2pe false ' + \
			'--rep1 %s --rep2 %s ' %(tas['rep1_ta'].get('file_id'), tas['rep2_ta'].get('file_id')) + \
			'--ctl1 %s --ctl2 %s ' %(tas['rep1_ta'].get('control_id'), tas['rep2_ta'].get('control_id')) + \
			'--genomesize %s --chrom_sizes "%s" ' %(args.gsize, args.csizes) + \
			'--blacklist "ENCODE Reference Files:/hg19/blacklists/wgEncodeDacMapabilityConsensusExcludable.bed.gz"'
		if args.debug:
			run_command += ' --debug'
		if args.idr:
			run_command += ' --idr --idrversion %s' %(args.idrversion)

		print run_command
		if args.dryrun:
			logging.info('Dryrun')
		else:
			try:
				subprocess.check_call(run_command, shell=True)
			except subprocess.CalledProcessError as e:
				logging.error("%s exited with non-zero code %d" %(workflow_spinner, e.returncode))
			else:
				print "%s workflow created" %(experiment['accession'])

if __name__ == '__main__':
	main()