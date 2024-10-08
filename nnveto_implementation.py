"""
To implement NN veto decision

USAGE:

run the following commands outside of the FairShiP environment:
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    pip install scikit-learn==1.4.0
    pip install torch_geometric
    pip install pyg_lib torch_scatter torch_sparse torch_cluster torch_spline_conv -f
then proceed with running the analysis script within FairShiP.
Example script below:
    usage:
     https://data.pyg.org/whl/torch-2.4.0+cpu.html   python nnveto_implementation.py

"""
#-----------------------------------------------------------------------------------------------------------
# Import functions
import ROOT,os,sys,getopt
import shipVeto

#-----------------------------------------------------------------------------------------------------------
    
path='/eos/experiment/ship/user/Iaroslava/NeutrinoSample2023/job_24_27'
geoFile='/geofile_full.conical.Genie-TGeant4.root'
fgeo = ROOT.TFile(path+geoFile)
sGeo   = fgeo.FAIRGeom


classification_list={0:"signal",1:"neuDIS",2:"muonDIS"}

 
def Main_function():
    
    for inputFile in os.listdir(path):
        
        if not inputFile.endswith('_rec.root'): continue 
            
        f = ROOT.TFile.Open(path + "/"+inputFile)
        sTree = f.cbmsim
        
        veto_ship=shipVeto.Task(sTree)

        nEvents = sTree.GetEntries()             

        for eventNr in range(200):
            
            rc = sTree.GetEvent(eventNr)
            
            print(eventNr)

            if not hasattr(sTree,'Particles'): continue

            candidate_id_in_event=0

            for signal in sTree.Particles:   
                
                candidate_id_in_event+=1
                
                UBT_veto,UBT_hits                       =   veto_ship.UBT_decision()                
                BasicSBT45_veto ,wBasicSBT45,HitsSBT45  =   veto_ship.SBT_decision(threshold=45)
                BasicSBT90_veto ,wBasicSBT90,HitsSBT90  =   veto_ship.SBT_decision(threshold=90)
                BasicSBT0_veto                          =   bool(len(sTree.Digi_SBTHits)) #any sbt activity

                NN_Veto_veto,classification             =   veto_ship.Veto_decision_NN() #candidate= also explicitly signal)
                # need to test GNN now
                GNN_Veto_veto, GNN_classification             =   veto_ship.Veto_decision_GNN() #candidate= also explicitly signal)

                classification=classification.item()    # default format is a tensor
                GNN_classification = GNN_classification.item()

                if NN_Veto_veto.item():    print("NN Veto - The event is not signal(0), must be :",classification_list[classification])
                else:
                    print("NN Veto - Signal found")
                if GNN_Veto_veto.item():    print("GNN Veto - The event is not signal(0), must be :",
                                           classification_list[GNN_classification])
                else:
                    print("GNN Veto - Signal found")


Main_function()
