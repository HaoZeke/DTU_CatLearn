import numpy as np
import copy
from scipy.linalg import cho_factor,cho_solve,eigh

class Object_functions:
    def __init__(self,**kwargs):
        " The object function that is used to optimize the hyperparameters "

    def hp(self,theta,parameters):
        " Make hyperparameter dictionary from lists"
        theta,parameters=np.array(theta),np.array(parameters)
        parameters_set=sorted(set(parameters))
        hp={para_s:self.numeric_limits(theta[parameters==para_s]) for para_s in parameters_set}
        return hp,parameters_set
    
    def numeric_limits(self,array,dh=0.1*np.log(np.finfo(float).max)):
        " Replace hyperparameters if they are outside of the numeric limits in log-space "
        return np.where(-dh<array,np.where(array<dh,array,dh),-dh)
    
    def update(self,TP,hp):
        " Update TP "
        TP=copy.deepcopy(TP)
        TP.set_hyperparams(hp)
        return TP
    
    def kxx_corr(self,TP,X,dis_m=None):
        " Get covariance matrix with or without noise correction"
        # Calculate the kernel with and without noise
        KXX=TP.kernel(X,get_derivatives=TP.use_derivatives,dis_m=dis_m)
        n_data=len(KXX)
        KXX=self.add_correction(TP,KXX,n_data)
        return KXX,n_data
    
    def add_correction(self,TP,KXX,n_data):
        " Add noise correction to covariance matrix"
        if TP.correction:
            corr=TP.get_correction(np.diag(KXX))
            KXX[range(n_data),range(n_data)]+=corr
        return KXX
        
    def kxx_reg(self,TP,X,dis_m=None):
        " Get covariance matrix with regularization "
        KXX=TP.kernel(X,get_derivatives=TP.use_derivatives,dis_m=dis_m)
        KXX_n=TP.add_regularization(KXX,len(X),overwrite=False)
        return KXX_n,KXX,len(KXX)
        
    def y_prior(self,X,Y,TP):
        " Update prior and subtract target "
        Y_p=Y.copy()
        TP.prior.update(X,Y_p)
        Y_p=Y_p-TP.prior.get(X)
        if TP.use_derivatives:
            Y_p=Y_p.T.reshape(-1,1)
        return Y_p,TP
    
    def coef_cholesky(self,TP,X,Y,dis_m):
        " Calculate the coefficients by using Cholesky decomposition "
        # Calculate the kernel with and without noise
        KXX_n,KXX,n_data=self.kxx_reg(TP,X,dis_m=dis_m)
        # Cholesky decomposition
        L,low=cho_factor(KXX_n)
        # Subtract the prior mean to the training target
        Y_p,TP=self.y_prior(X,Y,TP)
        # Get the coefficients
        coef=cho_solve((L,low),Y_p,check_finite=False)
        return coef,L,low,Y_p,KXX,n_data

    def get_eig(self,TP,X,Y,dis_m):
        " Calculate the eigenvalues " 
        # Calculate the kernel with and without noise
        KXX=TP.kernel(X,get_derivatives=TP.use_derivatives,dis_m=dis_m)
        n_data=len(KXX)
        KXX[range(n_data),range(n_data)]+=TP.get_correction(np.diag(KXX))
        # Eigendecomposition
        try:
            D,U=eigh(KXX)
        except:
            # More robust eigendecomposition, but slower
            D,U=eigh(KXX,driver='ev')
        # Subtract the prior mean to the training target
        Y_p,TP=self.y_prior(X,Y,TP)
        UTY=(np.matmul(U.T,Y_p)).reshape(-1)**2
        return D,U,Y_p,UTY,KXX,n_data
    
    def get_cinv(self,TP,X,Y,dis_m):
        " Get the inverse covariance matrix "
        coef,L,low,Y_p,KXX,n_data=self.coef_cholesky(TP,X,Y,dis_m)
        cinv=cho_solve((L,low),np.identity(n_data),check_finite=False)
        return coef,cinv,Y_p,KXX,n_data
    
    def logpriors(self,hp,parameters_set,parameters,prior=None,jac=False):
        " Log of the prior distribution value for the hyperparameters "
        if prior is None:
            return 0
        if not jac:
            return sum(
                np.sum(
                    [pr.ln_pdf(hp[para][p]) for p, pr in enumerate(prior[para])]
                )
                for para in set(hp.keys())
                if para in prior.keys()
            )
        lprior_deriv=np.array([])
        for para in parameters_set:
            if para in prior.keys():
                lprior_deriv=np.append(lprior_deriv,np.array([pr.ln_deriv(hp[para][p]) for p,pr in enumerate(prior[para])]))
            else:
                lprior_deriv=np.append(lprior_deriv,np.array([0]*parameters.count(para)))
        return lprior_deriv

    def get_K_inv_deriv(self,K_deriv,KXX_inv,multiple_para):
        " Get the diagonal elements of the matrix product of the inverse and derivative covariance matrix "
        return (
            np.array([np.einsum('ij,ji->', KXX_inv, K_d) for K_d in K_deriv])
            if multiple_para
            else np.einsum('ij,ji->', KXX_inv, K_deriv)
        )
    
    def get_solution(self,sol,TP,parameters,X,Y,prior,jac=False,dis_m=None):
        " Get the solution of the optimization in terms of hyperparameters and TP "
        hp,parameters_set=self.hp(sol['x'],parameters)
        sol['hp']=hp.copy()
        sol['TP']=self.update(TP,hp)
        return sol

    def function(self,theta,TP,parameters,X,Y,prior=None,jac=False,dis_m=None):
        " The function call that calculate the object function. "
        raise NotImplementedError()
