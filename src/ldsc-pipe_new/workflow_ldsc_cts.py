
from __future__ import print_function
import argparse
import configparser
import glob
import os
import subprocess
import re
import sys
import json

import string
import random

import make_annot_from_geneset_all_chr

###################################### USAGE ######################################
# Compatibility: Python 2 and 3

### Run in unbuffered mode
# time python -u workflow_ldsc_cts.py |& tee workflow_ldsc_cts.UNNAMED.out.txt

###################################### DOCS ######################################


###################################### DESCRIPTION ######################################


### Output
# This script will call ldsc.py to do prefix_genomic_annot regression.
# The following output files will be written to the --prefix_annot_files:
# <OUT>.cell_type_results.txt
# <OUT>.log


###################################### WIKI ######################################

### DOCS weights and baseline
# --ref-ld-chr /raid5/projects/timshel/sc-genetics/ldsc/data/1000G_EUR_Phase3_baseline/baseline.
# --ref-ld-chr /raid5/projects/timshel/sc-genetics/ldsc/data/baseline_v1.1/baseline.

# --w-ld-chr /raid5/projects/timshel/sc-genetics/ldsc/data/weights_hm3_no_hla/weights.
# --w-ld-chr /raid5/projects/timshel/sc-genetics/ldsc/data/1000G_Phase3_weights_hm3_no_MHC/weights.hm3_noMHC.


###################################### FUNCTIONS ######################################
def write_cts_file_filter(prefix_genomic_annot, file_multi_gene_set):
	""" 
	Write 'annotation filter' file based on annotations in file_multi_gene_set to use as input to make_cts_file.py. 
	This is to modify the default behavior of make_cts_file.py, which is to write a cts file for all annotations in /per_annotation/ directory.
	
	DESIGN [OUTDATED]:
	1) read log.{prefix_genomic_annot}.multi_geneset.txt file (generated by make_annot_from_geneset_all_chr.py)
		- this file ALWAYS contain the 3 columns: "annotation", "gene_input", "annotation_value"
		- this file ALWAYS contain ALL annotations in the out_dir.
	2) use unique annotations in file_multi_gene_set to filter file_multi_geneset_all.
	3) write file_cts_annotation_filter to /tmp/ dir 
	4) return file_cts_annotation_filter filename.
	"""
	print("Generating file_cts_annotation_filter...")
	str_random = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10)) # geneate random ascii string of len 10. REF: https://stackoverflow.com/a/2257449/6639640
	file_cts_annotation_filter = "{tmp_dir}/{prefix_genomic_annot}.{random}.txt".format(tmp_dir = TMP_DIR,
																						 prefix_genomic_annot = prefix_genomic_annot,
																						 random = str_random) # *OBS*: we add a random string to make sure any parallel processes are not trying to write to the same file as the same time.
	
	### Read existing multi_geneset containing ALL annotations
	# file_multi_geneset_all = "/scratch/sc-ldsc/{prefix_genomic_annot}/log.{prefix_genomic_annot}.multi_geneset.txt".format(prefix_genomic_annot=prefix_genomic_annot)
	# df_multi_geneset_all = pd.read_csv(file_multi_geneset_all, sep="\t", index_col=False)
	
	### Parse file_multi_gene_set
	df_multi_gene_set = make_annot_from_geneset_all_chr.read_multi_gene_set_file(file_multi_gene_set=file_multi_gene_set,
															 out_dir="{output_dir}/pre-computation/{prefix_genomic_annot}".format(prefix_genomic_annot=prefix_genomic_annot, output_dir = OUTPUT_DIR),
															 out_prefix=prefix_genomic_annot,
															 flag_encode_as_binary_annotation=False, # can be set to both True and False
															 flag_mouse=True if FLAG_WGCNA else False, 
															 flag_wgcna=True if FLAG_WGCNA else False,
															 print_log_files=False) # OBS: print_log_files=False is important
	annotations = df_multi_gene_set["annotation"].unique() # returns NumPy array.
	### Write file
	with open(file_cts_annotation_filter, "w") as fh_out:
		for annotation in annotations: 
			fh_out.write(str(annotation)+"\n")
	print("Wrote n={} annotations to file_cts_annotation_filter={}.".format(len(annotations), file_cts_annotation_filter))
	return file_cts_annotation_filter


def ldsc_pre_computation(prefix_genomic_annot, file_multi_gene_set):

	### Error checks
	if "__" in prefix_genomic_annot:
		raise ValueError("prefix_genomic_annot={} contains double underscore ('__'). These characters are reserved keywords for splitting files downstream in the pipeline.".format(prefix_genomic_annot))

	### Make annot
	if SNP_WINDOWS == True:
		cmd = "{PYTHON3_EXEC} snp_windows/Generate-SNP-windows.py \
		 --file_multi_gene_set {file_multi_gene_set} \
		 --input_dir {in_dir}\
		 --bimfile_basename {bimfile} \
		 --out_dir {output_dir}/pre-computation/{prefix_genomic_annot} \
		 --out_prefix {prefix_genomic_annot}".format(PYTHON3_EXEC=PYTHON3_EXEC,
			file_multi_gene_set=file_multi_gene_set, 
			prefix_genomic_annot=prefix_genomic_annot,
			output_dir=OUTPUT_DIR,
			in_dir = SNPSNAP_INPUT_DIR,
			bimfile=BIMFILES_BASENAME)



	else:###  *RESOURCE NOTES*: if you have many modules (~3000-6000) then set --n_parallel_jobs to ~2-5 (instead of 22). Otherwise the script will up all the MEMORY on yggdrasil and fail.
		cmd = """{PYTHON3_EXEC} {flag_unbuffered} make_annot_from_geneset_all_chr.py \
			--file_multi_gene_set {file_multi_gene_set} \
			--file_gene_coord  {file_gene_coordinates}\
			--windowsize {window_size} \
			--bimfile_basename {bimfiles_basename} \
			{flag_binary} \
			{flag_wgcna} \
			--out_dir {output_dir}/pre-computation/{prefix_genomic_annot} \
			--out_prefix {prefix_genomic_annot}
			""".format(PYTHON3_EXEC=PYTHON3_EXEC,
				flag_unbuffered="-u" if FLAG_UNBUFFERED else "", 
				file_multi_gene_set=file_multi_gene_set, 
				prefix_genomic_annot=prefix_genomic_annot, 
				flag_wgcna="--flag_wgcna --flag_mouse" if FLAG_WGCNA else "",
				flag_binary="--flag_encode_as_binary_annotation" if FLAG_BINARY else "",
				output_dir=OUTPUT_DIR,
				file_gene_coordinates = GENE_COORDINATES,
				window_size = WINDOW_SIZE_KB * 1000,
				bimfiles_basename = BIMFILES_BASENAME
				) 
	
	print("Running command: {}".format(cmd))
	p = subprocess.Popen(cmd, shell=True, bufsize=0 if FLAG_UNBUFFERED else -1)
	p.wait()
	print("Return code: {}".format(p.returncode))
	if not p.returncode == 0:
		raise Exception("make_annot_from_geneset_all_chr.py: Got non zero return code running command:\n{}".format(cmd))


	### compute LD scores
	### *RESOURCE NOTES*: this script uses a lot of CPU. Never run more than 4 parallel jobs. 4 parallel jobs will use ~220% CPU
	cmd="{PYTHON3_EXEC} {flag_unbuffered} wrapper_compute_ldscores.py --prefix_annot_files {output_dir}/pre-computation/{prefix_genomic_annot}/ --n_parallel_jobs 2".format(PYTHON3_EXEC=PYTHON3_EXEC,
																																								flag_unbuffered="-u" if FLAG_UNBUFFERED else "", 
																																								prefix_genomic_annot=prefix_genomic_annot,
																																								output_dir=OUTPUT_DIR)
	print("Running command: {}".format(cmd))
	p = subprocess.Popen(cmd, shell=True, bufsize=0 if FLAG_UNBUFFERED else -1)
	p.wait()
	print("Return code: {}".format(p.returncode))
	# RUNTIME ----> ~6 h for ~500 modules with --n_parallel_jobs=4
	if not p.returncode == 0:
		raise Exception("wrapper_compute_ldscores.py: Got non zero return code running command:\n{}".format(cmd))

	### split LD scores
	### This script will read 1 ".COMBINED_ANNOT.$CHR.l2.ldscore.gz" file  (N_SNPs x N_ANNOTATION) per parallel process.
	###  *RESOURCE NOTES*: this script does not use much memory (it uses < 10-50GB?) and can easy be run with full parallelization (n=22)
	cmd="{PYTHON3_EXEC} {flag_unbuffered} split_ldscores.py --prefix_ldscore_files {output_dir}/pre-computation/{prefix_genomic_annot}/ --n_parallel_jobs 22".format(PYTHON3_EXEC=PYTHON3_EXEC,
																																								flag_unbuffered="-u" if FLAG_UNBUFFERED else "", 
																																								prefix_genomic_annot=prefix_genomic_annot,
																																								output_dir=OUTPUT_DIR)
	print("Running command: {}".format(cmd))
	p = subprocess.Popen(cmd, shell=True, bufsize=0 if FLAG_UNBUFFERED else -1)
	p.wait()
	print("Return code: {}".format(p.returncode))
	# RUNTIME ----> ~10 min
	if not p.returncode == 0:
		raise Exception("split_ldscores.py: Got non zero return code running command:\n{}".format(cmd))

	### Write CTS filter
	file_cts_annotation_filter = write_cts_file_filter(prefix_genomic_annot, file_multi_gene_set)
	sys.stdout.flush()

	### make cts file
	###  *RESOURCE NOTES*: this script is light-weight and uses no computational resources
	cmd="{PYTHON3_EXEC} {flag_unbuffered} make_cts_file.py --prefix_ldscore_files {output_dir}/pre-computation/{prefix_genomic_annot}/per_annotation/ --cts_outfile {output_dir}/pre-computation/{prefix_genomic_annot}.ldcts.txt --annotation_filter {file_cts_annotation_filter}".format(PYTHON3_EXEC=PYTHON3_EXEC,
																																																																								  flag_unbuffered="-u" if FLAG_UNBUFFERED else "", 
																																																																								  prefix_genomic_annot=prefix_genomic_annot,
																																																																								  file_cts_annotation_filter=file_cts_annotation_filter,
																																																																								  output_dir=OUTPUT_DIR)
	# ^*OBS***:DIRTY USING  as prefix in  {prefix_genomic_annot}.ldcts.txt. FIX THIS.
	print("Running command: {}".format(cmd))
	p = subprocess.Popen(cmd, shell=True, bufsize=0 if FLAG_UNBUFFERED else -1)
	p.wait()
	print("Return code: {}".format(p.returncode))
	# RUNTIME ----> 0 min
	if not p.returncode == 0:
		raise Exception("make_cts_file.py: Got non zero return code running command:\n{}".format(cmd))



###################################### UTILS - ALL GENES ######################################


def get_all_genes_ref_ld_chr_name(dataset):
	""" Function to get the ref_ld_chr_name for 'all genes annotation' for ldsc.py --h2/--h2-cts command """
	# *IMPORTANT*: ldsc_all_genes_ref_ld_chr_name MUST be full file path PLUS trailing "."
	dict_dataset_all_genes_path_prefix = {"mousebrain":"{output_dir}/pre-computation/control.all_genes_in_dataset/per_annotation/control.all_genes_in_dataset__all_genes_in_dataset.mousebrain.".format(output_dir = OUTPUT_DIR),
						 				"tabula_muris":"{output_dir}/pre-computation/control.all_genes_in_dataset/per_annotation/control.all_genes_in_dataset__all_genes_in_dataset.tabula_muris.".format(output_dir = OUTPUT_DIR),
						 				"campbell":"{output_dir}/pre-computation/control.all_genes_in_dataset/per_annotation/control.all_genes_in_dataset__all_genes_in_dataset.campbell.".format(output_dir = OUTPUT_DIR),
						 				"tasic":"{output_dir}/pre-computation/control.all_genes_in_dataset/per_annotation/control.all_genes_in_dataset__all_genes_in_dataset.tasic.".format(output_dir = OUTPUT_DIR),
						 				"chen":"{output_dir}/pre-computation/control.all_genes_in_dataset/per_annotation/control.all_genes_in_dataset__all_genes_in_dataset.chen.".format(output_dir = OUTPUT_DIR),
						 				 "dataset_with_no_all_genes":"" # value must be empty string.
						 				 }
	if not dataset in dict_dataset_all_genes_path_prefix:
		raise KeyError("dataset={} is not found in dict_dataset_all_genes_path_prefix.".format(dataset))
	ldsc_all_genes_ref_ld_chr_name = dict_dataset_all_genes_path_prefix[dataset]
	if ldsc_all_genes_ref_ld_chr_name: # only needed to support dataset_with_no_all_genes (empty string valuates false)
		# some obnoxious validation of the matches
		files_ldscore = glob.glob("{}*l2.ldscore.gz".format(ldsc_all_genes_ref_ld_chr_name)) # get ldscore files for all chromosomes. glob() returns full file paths.
		if not len(files_ldscore) == 22: # we must have ldscore files for every chromosome, so the length 
			raise ValueError("dataset={} only has n={} matching {}*l2.ldscore.gz files. Expected 22 files. Check the ldscore file directory or update the dict_dataset_all_genes_path_prefix inside this function.".format(dataset, len(files_ldscore), ldsc_all_genes_ref_ld_chr_name))
	return(ldsc_all_genes_ref_ld_chr_name)


###################################### Job scheduler ######################################

def job_scheduler(list_cmds, n_parallel_jobs):
	""" Schedule parallel jobs with at most n_parallel_jobs parallel jobs."""
	list_of_processes = []
	batch = 1
	for i, cmd in enumerate(list_cmds, start=1):
		print("job schedule batch = {} | i = {} | Running command: {}".format(batch, i, cmd))
		## p = subprocess.Popen(cmd, shell=True, bufsize=0 if FLAG_UNBUFFERED else -1, stdout=FNULL, stderr=subprocess.STDOUT)
		### You need to keep devnull open for the entire life of the Popen object, not just its construction. 
		### FNULL = open(os.devnull, 'w') # devnull filehandle does not need to be closed?
		p = subprocess.Popen(cmd, shell=True, bufsize=0 if FLAG_UNBUFFERED else -1)
		list_of_processes.append(p)
		print("job schedule batch = {} | i = {} | PIDs of running jobs (list_of_processes):".format(batch, i))
		print(" ".join([str(p.pid) for p in list_of_processes])) # print PIDs
		if i % n_parallel_jobs == 0: # JOB BATCH SIZE
			batch += 1
			for p in list_of_processes:
				print("=========== Waiting for process: {} ===========".format(p.pid))
				sys.stdout.flush()
				p.wait()
				print("Returncode = {}".format(p.returncode))
			list_of_processes = [] # 'reset' list

	### wait for the rest for the rest of the processes
	for p in list_of_processes:
		print("=========== Waiting for process: {} ===========".format(p.pid))
		p.wait()

	return list_of_processes

if __name__ == "__main__":


	#########################################################################################
	###################################### PARSE VARIABLES ##################################
	#########################################################################################
	
	## Command line options
	parser = argparse.ArgumentParser()

	parser.add_argument("--binary", action='store_true', help="Produce a binary annotation file to calculate LDSC with.")
	parser.add_argument("--wgcna", action='store_true', help="Tells the script that the input multi-geneset file is from WGCNA.")
	parser.add_argument("--windowsize", type=int, default=100, help="Specify an alternate window size in kb, default is 100.")
	parser.add_argument("--buffered", action='store_true', help="Set the output to be buffered rather than the default unbuffered.")
	parser.add_argument("--snp", action='store_true', help="Tells the script that the input multi-geneset file is from WGCNA.")

	args = parser.parse_args()
	
	FLAG_BINARY = args.binary
	FLAG_WGCNA = args.wgcna
	WINDOW_SIZE_KB = args.windowsize
	FLAG_UNBUFFERED = not args.buffered
	SNP_WINDOWS = args.snp


	## Config file
	config = configparser.SafeConfigParser(os.environ)
	config.read('workflow_ldsc_config.ini')

	# Paths
	PYTHON2_EXEC = config['PATHS']['PYTHON2_EXEC']
	PYTHON3_EXEC = config['PATHS']['PYTHON3_EXEC']
	PATH_LDSC_SCRIPT = config['PATHS']['PATH_LDSC_SCRIPT']
	OUTPUT_DIR = config['PATHS']['OUTPUT_DIR']
	GENE_COORDINATES = config['PATHS']['GENE_COORDINATES']
	BIMFILES_BASENAME = config['PATHS']['BIMFILES_BASENAME']
	TMP_DIR = config['PATHS']['TMP_DIR']
	GWAS_DIRECTORY = config['PATHS']['GWAS_DIRECTORY']
	SNPSNAP_INPUT_DIR = config['PATHS']['SNPSNAP_INPUT_DIR']
	MULTIGENESET_DIRECTORY = config['PATHS']['MULTIGENESET_DIRECTORY']

	# GWAS summary stat locations
	LIST_GWAS = config['GWAS']['SUMSTAT_FILES'].splitlines()

	# LDSC
	BASELINE = config['LDSC']['BASELINE']
	LD_SCORE_WEIGHTS = config['LDSC']['LD_SCORE_WEIGHTS']

	# Parallelisation of scripts
	N_PARALLEL_LDSC_REGRESSION_JOBS = int(config['PARALLEL']['LDSC_REGRESSION'])


	#########################################################################################
	###################################### PRE-PROCESS ######################################
	#########################################################################################


	dict_genomic_annot = {"celltypes.chen.bmi.192306":
 					  	{"dataset":"chen",
 					  	"file_multi_gene_set":"{multigeneset_directory}/multi_geneset.chen.ESmu.bmi_es_190623.txt".format(multigeneset_directory = MULTIGENESET_DIRECTORY)}
 					 }
	### Make sure that all_genes annotation is present, so program does not fail later on.
	for prefix_genomic_annot in dict_genomic_annot.keys():
		param_dict = dict_genomic_annot[prefix_genomic_annot]
		ldsc_all_genes_ref_ld_chr_name = get_all_genes_ref_ld_chr_name(param_dict["dataset"])

	### Run pre-computation
	for prefix_genomic_annot in list(dict_genomic_annot.keys()): # list() needed for py3 compatibility. REF: https://stackoverflow.com/a/11941855/6639640
		param_dict = dict_genomic_annot[prefix_genomic_annot]
		try:
			ldsc_pre_computation(prefix_genomic_annot, param_dict["file_multi_gene_set"])
		except Exception as e:
			print("Caught exception during ldsc_pre_computation for prefix_genomic_annot={}.".format(prefix_genomic_annot))
			print("Exception: {}".format(e))
			print("Will drop prefix_genomic_annot={} from dict_genomic_annot and not do any further computations on this prefix_genomic_annot.".format(prefix_genomic_annot))
			dict_genomic_annot.pop(prefix_genomic_annot, None) # drop key from dict while iterating over it. REF: https://stackoverflow.com/questions/5384914/how-to-delete-items-from-a-dictionary-while-iterating-over-it and https://stackoverflow.com/a/11277439/6639640

	#########################################################################################
	###################################### RUN LDSC PRIM ######################################
	#########################################################################################

	### Create job commands
	list_cmds_ldsc_prim = []
	for prefix_genomic_annot, param_dict in dict_genomic_annot.items():
		ldsc_all_genes_ref_ld_chr_name = get_all_genes_ref_ld_chr_name(param_dict["dataset"])
		flag_all_genes = True
		if ldsc_all_genes_ref_ld_chr_name=="":
			print("OBS: Running without all_genes correction.")
			flag_all_genes = False
		for gwas in LIST_GWAS:
			fileout_prefix = "{output_dir}/out/out.ldsc/{prefix_genomic_annot}__{gwas}".format(gwas=gwas, prefix_genomic_annot=prefix_genomic_annot, output_dir=OUTPUT_DIR)
			if os.path.exists("{}.cell_type_results.txt".format(fileout_prefix)):
				print("GWAS={}, prefix_genomic_annot={} | LDSC output file exists: {}. Will skip this LDSC regression...".format(gwas, prefix_genomic_annot, fileout_prefix))
				continue
			### I'm 90% sure that ldsc.py ONLY runs on python2 - and not python3.
			### *OBS*: we are runnin ldsc python script with UNBUFFERED stdout and stderr
			### REF: https://stackoverflow.com/questions/230751/how-to-flush-output-of-print-function
			### python -u: Force the stdout and stderr streams to be unbuffered. THIS OPTION HAS NO EFFECT ON THE STDIN STREAM [or writing of other files, e.g. the ldsc .log file]. See also PYTHONUNBUFFERED.
			cmd = """{PYTHON2_EXEC} {flag_unbuffered} {script} --h2-cts {gwas_directory}/{gwas}.sumstats.gz \
			--ref-ld-chr {baseline_path}{flag_all_genes}{ldsc_all_genes_ref_ld_chr_name} \
			--w-ld-chr {ld_score_weights} \
			--ref-ld-chr-cts {output_dir}/pre-computation/{prefix_genomic_annot}.ldcts.txt \
			--out {fileout_prefix}""".format(
				PYTHON2_EXEC=PYTHON2_EXEC,
				flag_unbuffered="-u" if FLAG_UNBUFFERED else "",
				script=PATH_LDSC_SCRIPT,
				gwas=gwas,
				gwas_directory = GWAS_DIRECTORY,
				prefix_genomic_annot=prefix_genomic_annot,
				flag_all_genes="," if flag_all_genes else "",
				ldsc_all_genes_ref_ld_chr_name=ldsc_all_genes_ref_ld_chr_name,
				output_dir = OUTPUT_DIR,
				fileout_prefix=fileout_prefix,
				baseline_path = BASELINE,
				ld_score_weights = LD_SCORE_WEIGHTS
				)
			list_cmds_ldsc_prim.append(cmd)


	### Call scheduler
	job_scheduler(list_cmds=list_cmds_ldsc_prim, n_parallel_jobs=N_PARALLEL_LDSC_REGRESSION_JOBS)


	###################################### XXXX ######################################


	print("Script is done!")



