#!/bin/bash
#######################################################################################

#ClusterId=	$1
#ProcId=		$2
#Runnumber=	$3

#######################################################################################
source /cvmfs/ship.cern.ch/24.10/setUp.sh 
#alienv load FairShip/latest-master-release > config_<version>.sh
source /afs/cern.ch/user/a/areghuna/config_ECN3_2024.sh
echo 'config sourced'
#######################################################################################
python /afs/cern.ch/user/a/areghuna/William/sbtveto/data_preprocessing/candidate_MuBack_dataformatter.py --muDIS --jobDir "$3" --startEvent "$4"
#should always have the whole path for condor to work

xrdcp datafile_muDIS_*.h5 /eos/experiment/ship/user/anupamar/NN_data/h5_files/wMuonBack/
xrdcp datafile_muDIS_*.root /eos/experiment/ship/user/anupamar/NN_data/root_files/wMuonBack/

