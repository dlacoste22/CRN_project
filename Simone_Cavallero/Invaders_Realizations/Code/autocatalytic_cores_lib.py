import pandas as pd #to export results to excel files and handle data frames
import numpy as np #to handle matrices
import gurobipy as gb #for solving the optimization problems


###Class for the model

class Model(object):
    """A class to model the Gurobi model and gb.tupledicts of variables"""
    def __init__(self,model: gb.Model, x: gb.tupledict, y: gb.tupledict, z: gb.tupledict, w: gb.tupledict):
      self.model = model
      self.x = x
      self.y = y
      self.z = z
      self.w = w

# =============================================================================
# Load the optimization model for computing the autocatalytic subnetworks
# Input: SM: stoichiometric matrix

# Output:
#        model: opt model
#        df: dattaframe with results
# =============================================================================


def OptModel_AutocatalyticCores(SM, NumReact=0) -> Model:


    n=SM.shape[0]
    m=SM.shape[1]
    
    
    #print("NamesSp: ", namesSp)
    
    
    M=range(m)
    N=range(n)

    

    model = gb.Model('ModelCycles')
    
    UB=100
    y=model.addVars(n,  vtype=gb.GRB.BINARY,  name="y") # core species
    w = model.addVars(n, vtype=gb.GRB.BINARY,name="w") #species present but not core
    x = model.addVars(m, ub=1, name="x") #flux: normalized to [0,1]
    z = model.addVars(m, vtype=gb.GRB.BINARY,name="z") #support of flux vectors
    P={} #production vector: P_i = SM_i x
    for i in N:
        P[i]=gb.quicksum(SM[i,j]*x[j] for j in M)
        
    


    obj=gb.quicksum(z[j] for j in M) + (1/UB)*gb.quicksum(x[j] for j in M) #minimize number of reactions in the core
    model.setObjective(obj, gb.GRB.MINIMIZE)
    
    if NumReact>=1:
        model.addConstr(gb.quicksum(z[j] for j in M)== NumReact) #at least two reactions
        
    
    model.addConstr(gb.quicksum(z[j] for j in M)>= 2) #at least two reactions
    for j in M:
        model.addConstr(x[j]<= z[j]) #support
        for i in N:
            if abs(SM[i,j])>0.5:
                model.addConstr(y[i]+w[i]>=z[j]) #species in the reaction must be core or non-core present
        for j1 in range(j):
            if all(SM[:,j1]==-SM[:,j]):  #Incompatible reverse reactions in the core     
                model.addConstr(z[j]+z[j1]<=1)
        model.addConstr(gb.quicksum(y[i] for i in N if SM[i,j]>0.5)>=z[j]) #if the reaction is in the core, both positive and negative entries in the core species are needed
        model.addConstr(gb.quicksum(y[i] for i in N if SM[i,j]<-0.5)>=z[j])
            
    for i in N:
        model.addConstr(gb.quicksum(z[j] for j in M if SM[i,j]>0.5)>=y[i]) # if species i is core, then, a reaction for which its coefficiente is negative and positive is needed.
        model.addConstr(gb.quicksum(z[j] for j in M if SM[i,j]<-0.5)>=y[i])
        model.addConstr(gb.quicksum(z[j] for j in M if abs(SM[i,j])>0.5)>=w[i]) # if i is non-core present, a reaction must use that species

        model.addConstr(y[i]+w[i]<=1) #i can be either core or non-core present but not both
        bigM=sum(-SM[i,j] for j in M if SM[i,j]<0)*UB
        Neg=[j for j in M if SM[i,j]<-0.01]
        Pos=[j for j in M if SM[i,j]>0.01]
        if len(Neg)>=1 and len(Pos)>=1:
            model.addConstr(P[i] >=0.001 - bigM*(1-y[i]))
        else:
            y[i].ub=0

    # number of reactions and cores must coincide:            
    model.addConstr(gb.quicksum(y[i] for i in N) == gb.quicksum(z[j] for j in M))
    

                            
    model.Params.Outputflag=0
    model.update()
    
    smodel = Model(model,x,y,z,w)
    
    return smodel

    


def ConstructDataFrame(n: int, m:int):

    N=range(n)
    M=range(m)

    col=["AC"] + ["NumReact"] + ["F%d"%(i+1) for i in N] + ["M%d"%(i+1) for i in N] + ["R%d"%(j+1) for j in M] + ["W%d"%(i+1) for i in N] + ["EM%d"%(i+1) for i in N]  +["X%d"%(j+1) for j in M] + ["Zeroes"]#+ ["X%d"%(j+1) for j in M]

    df = pd.DataFrame(columns=col)
        
    return df
    
    
def ComputeAutocatalyticCores(SM, Excelfile: str, txtfile="", namesSp=[], namesRe=[], NumReact=0):
    
    ##1. Construct Data Frame:
    n=SM.shape[0]
    m=SM.shape[1]
    N=range(n)
    M=range(m)
    
    df = ConstructDataFrame(n,m)
    
    if txtfile!="":
        f = open(txtfile, "w")
        print("#Species: ", n, "# Reactions: ", m, file=f)
        f.close()
    else:
        print("#Species: ", n, "# Reactions: ", m)
        
    print("#Species: ", n, "# Reactions: ", m)
    print("Generating Autocatalytic Cycles...")
    
    
    ##2 Looad names for Species and Reactions
    if len(namesSp)==0:
        species=["C_%d"%(i+1) for i in N]
        species[0]="C"
    else:
        species=namesSp
        
    if len(namesRe)==0:
        reactions=["R%d"%(j+1) for j in M]
    else:
        reactions=namesRe
        
        
    
    ##3. Load Initial Model
    smodel=OptModel_AutocatalyticCores(SM, NumReact)
    model = smodel.model
    x = smodel.x
    y = smodel.y
    z = smodel.z 
    w = smodel.w
    
    
    #Initialize status
    status=gb.GRB.OPTIMAL
    
    cnt=0
    TotalTime=0
    #While the problem is feasible:
    while status==gb.GRB.OPTIMAL:
        
        model.optimize()
        
        status=model.status
        
        if status==gb.GRB.OPTIMAL:
            
            if (cnt+1)%5 ==0:
                print(cnt+1, " ", end=' ..')
            #Load solutions on core species
            
            Member=[round(y[i].x) for i in N]
            Reactions=[round(z[j].x) for j in M]
            Flows=[round(x[j].x,2) for j in M]
            
            ZZ=[j for j in M if z[j].x>0.5]
            YY=[i for i in N if y[i].x>0.5]
            
            Food=n*[0]
            Waste=n*[0]
            ExtraM=n*[0]
            for i in N:
                if w[i].x>0.5:
                    L=[SM[i,j] for j in M if z[j].x>0.5]
                    if all(l<0.001 for l in L):
                        Food[i]=1
                    elif all(l>-0.001 for l in L):
                        Waste[i]=1
                    else:
                        ExtraM[i]=1

            
            
            SS=np.empty((sum(Member), sum(Reactions)))

            for j in range(len(ZZ)):
                for i in range(len(YY)):
                    SS[i,j]=SM[YY[i],ZZ[j]]

            zeros=len(YY)*len(YY) - np.count_nonzero(SS)
            
            cnt+=1
            
            df.loc[cnt-1]=[cnt]+[len(ZZ)]+Food+Member+Reactions+Waste+ExtraM+Flows +[zeros]

          


        
            Time=model.RunTime
            TotalTime+=Time
        
            PrintSol(cnt, SM, Food, Waste, ExtraM, Member, Reactions, Flows, Time, zeros, species,reactions, txtfile=txtfile)
            #PrintSolLatex(cnt, SM, Food, Waste, ExtraM, Member, Reactions, Flows, Time, zeros, txtfile, species, reactions)

            #Update Model with Incompatibilities:
            
            model.addConstr(gb.quicksum(z[j] for j in M if Reactions[j]>0.5) <=sum(Reactions)-1)
        else:
            df.set_index("AC", inplace=True)
            df.to_excel(Excelfile)
            print("\n\n# Autocatalytic Cycles: %d"%(cnt))
            print("Consumed Time: %.2f secs."%(TotalTime))
            print("Saved in %s"%(Excelfile))
            
            
    return df
        

def PrintSol(cnt, SM, Food, Waste, ExtraM, Member, Reactions, Flow, Time, zeros, species,reactions, txtfile=""):
    
    n=SM.shape[0]
    m=SM.shape[1]
    N=range(n)
    M=range(m)
    
    
           
                    

    if txtfile!="":
        
        f = open(txtfile, "a")
        print("**** Sol %d: %d reactions"%(cnt, sum(Reactions)), file=f)
        
        
        YY=[i for i in N if Member[i]>0.5]  
        ZZ=[j for j in M if Reactions[j]>0.5]  
        UU=[] #Food
        WW=[] #Waste
        QQ=[] #Member non core
        for i in N:
            if i not in YY and sum(abs(SM[i,j]) for j in ZZ)>0.01:
                L=[SM[i,j] for j in ZZ]
                if all(l<0.001 for l in L):
                    UU.append(i)
                elif all(l>-0.001 for l in L):
                    WW.append(i)
                else:
                    QQ.append(i)
            
                    
                    
        #Labeled lists:

        Y=[species[i] for i in YY]
        U=[species[i] for i in UU] 
        W=[species[i] for i in WW]
        Q=[species[i] for i in QQ]
        Z=[reactions[j] for j in M if Reactions[j]>0.5]
        T=[round(sum(SM[i,j]*Flow[j] for j in M),2) for i in YY]  
    
        print("\t #Species: ", len(YY), "#FoodSet: ", len(UU), "#WasteSet: ",len(W),"#ExtraMembersSet: ",len(Q), "#Reactions: ", len(Z), file=f)
        print("\t Food Set", U, file=f)
        print("\t Waste Set", W, file=f)  
        print("\t Extra M in AC: ", Q, file=f)   
        print("\t Species in AC: ", Y, file=f)
    
        print("\t Reactions in AC: ", Z, file=f)
        
        print("\t Flow: ", [Flow[j] for j in M if Flow[j]>0.001], "--> Production: ", T, file=f)
    
                 
                      
       
        #print("Z0: ", Z0)
        for j in ZZ:
            #print([(i+1)*s[i,j].x for i in N if s[i,j].x>0.5], [p[i,j].x for i in N],[q[i,j].x for i in N], [t[i,j].x for i in N])
            Re=[i for i in N if SM[i,j] <= -0.9]
            PP=[i for i in N if SM[i,j] >=  0.9]
            cnt=0
            print("\t\t\t %s: "%reactions[j], end='', file=f)
            for i in Re:
                if cnt<len(Re)-1:
                    if -SM[i,j]<=1.1:
                        print("%s+"%(species[i]), end='', file=f)
                    else:
                        print("%d%s+"%(-SM[i,j], species[i]), end='', file=f)
                    cnt+=1
                else:
                    if -SM[i,j]<=1.1:
                        print("%s ->"%species[i], end='', file=f)
                    else:
                        print("%d%s ->"%(-SM[i,j], species[i]),end='', file=f)
            cnt=0
            for i in PP:
                if cnt<len(PP)-1:
                    if SM[i,j]<=1.1:
                        print("%s+"%(species[i]), end='', file=f)
                    else:
                        print("%d%s+"%(SM[i,j], species[i]), end='', file=f)
                    cnt+=1
                else:
                    if SM[i,j]<=1.1:
                        print("%s"%(species[i]), file=f)
                    else:
                        print("%d%s"%(SM[i,j], species[i]), file=f)
        print("\t - CPU Time: %.2f secs"%Time, file=f)    
        f.close()
    else:

        print("**** Sol %d: %d reactions"%(cnt, sum(Reactions)))
        
        
        YY=[i for i in N if Member[i]>0.5]  
        ZZ=[j for j in M if Reactions[j]>0.5]  
        UU=[] #Food
        WW=[] #Waste
        QQ=[] #Member non core
        for i in N:
            if i not in YY and sum(abs(SM[i,j]) for j in ZZ)>0.01:
                L=[SM[i,j] for j in ZZ]
                if all(l<0.001 for l in L):
                    UU.append(i)
                elif all(l>-0.001 for l in L):
                    WW.append(i)
                else:
                    QQ.append(i)
            
                    
                    
        #Labeled lists:

        Y=[species[i] for i in YY]
        U=[species[i] for i in UU] 
        W=[species[i] for i in WW]
        Q=[species[i] for i in QQ]
        Z=[reactions[j] for j in M if Reactions[j]>0.5]
        T=[round(sum(SM[i,j]*Flow[j] for j in M),2) for i in YY]  
    
        print("\t #Species: ", len(YY), "#FoodSet: ", len(UU), "#WasteSet: ",len(W),"#ExtraMembersSet: ",len(Q), "#Reactions: ", len(Z))
        print("\t Food Set", U)
        print("\t Waste Set", W)  
        print("\t Extra M in AC: ", Q)   
        print("\t Species in AC: ", Y)
    
        print("\t Reactions in AC: ", Z)
        
        print("\t Flow: ", [Flow[j] for j in M if Flow[j]>0.001], "--> Production: ", T)
    
                 
                      
       
        #print("Z0: ", Z0)
        for j in ZZ:
            #print([(i+1)*s[i,j].x for i in N if s[i,j].x>0.5], [p[i,j].x for i in N],[q[i,j].x for i in N], [t[i,j].x for i in N])
            Re=[i for i in N if SM[i,j] <= -0.9]
            PP=[i for i in N if SM[i,j] >=  0.9]
            cnt=0
            print("\t\t\t %s: "%reactions[j], end='')
            for i in Re:
                if cnt<len(Re)-1:
                    if -SM[i,j]<=1.1:
                        print("%s+"%(species[i]), end='')
                    else:
                        print("%d%s+"%(-SM[i,j], species[i]), end='')
                    cnt+=1
                else:
                    if -SM[i,j]<=1.1:
                        print("%s ->"%species[i], end='')
                    else:
                        print("%d%s ->"%(-SM[i,j], species[i]),end='')
            cnt=0
            for i in PP:
                if cnt<len(PP)-1:
                    if SM[i,j]<=1.1:
                        print("%s+"%(species[i]), end='')
                    else:
                        print("%d%s+"%(SM[i,j], species[i]), end='')
                    cnt+=1
                else:
                    if SM[i,j]<=1.1:
                        print("%s"%(species[i]))
                    else:
                        print("%d%s"%(SM[i,j], species[i]))
        print("\t - CPU Time: %.2f secs"%Time)    

        
         