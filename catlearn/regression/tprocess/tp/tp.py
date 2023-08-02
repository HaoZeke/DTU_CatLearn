import numpy as np
import copy
from scipy.linalg import cho_factor,cho_solve

class TProcess:
    def __init__(self,prior=None,kernel=None,hp={'noise':[-8.0]},use_derivatives=False,correction=True,hpfitter=None,a=1e-20,b=1e-20):
        """The Student's T Process Regression solver with Cholesky decomposition and optimization of hyperparameters.
            Parameters:
                prior : Prior class
                    The prior given for new data.
                kernel : Kernel class
                    The kernel function used for the kernel matrix.
                hp : dictionary
                    A dictionary of hyperparameters like noise and length-scale.
                use_derivatives : bool
                    Use derivatives/gradients for training and predictions.
                hpfitter: HyperparameterFitter class
                    A class to optimize hyperparameters.
                a : float
                    Hyperprior parameter for the inverse-gamma distribution of the prefactor.
                b : float
                    Hyperprior parameter for the inverse-gamma distribution of the prefactor.
        """
        #Kernel
        if kernel is None:
            from ..kernel import SE,SE_Derivative
            kernel=SE_Derivative(use_fingerprint=False) if use_derivatives else SE(use_fingerprint=False)
        self.kernel=copy.deepcopy(kernel)
        #Prior
        if prior is None:
            from ..means.mean import Prior_mean
            prior=Prior_mean()
        self.prior=copy.deepcopy(prior)
        #Whether to use derivatives or not for the target
        self.use_derivatives=use_derivatives
        # Use noise correction
        self.correction=correction
        #The hyperparameter optimization method
        if hpfitter is None:
            from ..hpfitter import HyperparameterFitter
            from ..objectfunctions import LogLikelihood
            hpfitter=copy.deepcopy(HyperparameterFitter(LogLikelihood()))
        self.set_hpfitter(hpfitter)
        # Check if the attributes agree
        self.check_attributes()
        #Set hyperparameters
        self.hp={}
        self.set_hyperparams(hp)
        # Hyperprior parameters
        self.a=a
        self.b=b

    
    def train(self,features,targets):
        """Train the T process with training features and targets. 
        Parameters:
            features : (N,D) array
                Training features with N data points and D dimensions
            targets : (N,1) array
                Training targets with N data points 
            or 
            targets : (N,1+D) array
                Training targets in first column and derivatives of each feature in the next columns if use_derivatives is True
        Returns trained T process:
        """
        #Make kernel matrix with noise
        self.features=features.copy()
        K=self.kernel(features,get_derivatives=True)
        K=self.add_regularization(K,len(features))
        self.L,self.low=cho_factor(K)
        #Subtracting prior mean from target 
        targets=targets.copy()
        self.prior.update(features,targets)
        targets=targets-self.prior.get(features)
        #Rearrange targets if derivatives are used
        if self.use_derivatives:
            targets=targets.T.reshape(-1,1)
        else:
            targets=targets[:,0:1].copy()
        #Calculate the coefficients
        self.coef=cho_solve((self.L,self.low),targets,check_finite=False)
        n2=len(targets)-2 if len(targets)>1 else 0
        self.delta=(2*self.b+np.matmul(targets.T,self.coef).item(0))/(2*self.a+n2)
        return self

    def predict(self,features,get_variance=False,get_derivatives=False,include_noise=False):
        """Predict the mean and variance for test features by using data and coefficients from training data.
        Parameters:
            features : (M,D) array
                Test features with M data points and D dimensions
            get_variance : bool
                Whether to predict the vartiance
            get_derivatives : bool
                Whether to predict the derivative mean and uncertainty
            include_noise : bool
                Whether to include the noise of data in the predicted variance
        Returns:
            Y_predict : (M,1) array 
                The predicted mean values
            or 
            Y_predict : (M,1+D) array
                The predicted mean values and derivatives
            var : (M,1) array
                The predicted variance of values
            or 
            var : (M,1+D) array
                The predicted variance of values and derivatives
        """
        #Calculate the kernel matrix of test and training data
        KQX=self.kernel(features,self.features,get_derivatives=get_derivatives)
        n_data=len(features)
        #Calculate the predicted values
        Y_predict=np.matmul(KQX,self.coef)
        #Check if the derivatives are calculated
        if len(Y_predict)==n_data:
            get_derivatives=False
        Y_predict=Y_predict.reshape(n_data,-1,order='F')
        Y_predict=Y_predict+self.prior.get(features,get_derivatives=get_derivatives)
        #Calculate the predicted variance
        if get_variance:
            var=self.calculate_variance(features,KQX,get_derivatives=get_derivatives,include_noise=include_noise)
            return Y_predict,var
        return Y_predict

    def calculate_variance(self,features,KQX,get_derivatives=False,include_noise=False):
        """Calculate the predicted variance
        Parameters:
            features : (M,D) array
                Test features with M data points and D dimensions.
            KQX : (M,N) array or (M*(1+D),N*(1+D)) array or (M,N*(1+D))
                The kernel matrix of test and training data.
            get_derivatives : bool
                Whether to predict the derivative uncertainty.
            include_noise : bool
                Whether to include the noise of data in the predicted variance
        Returns:
            var : (M,1) array
                The predicted variance of values.
            or 
            var : (M,1+D) array
                The predicted variance of values and derivatives.
        """
        #Calculate the diagonal elements of the kernel matrix without noise 
        n_data=len(features)
        k=self.kernel.diag(features,get_derivatives=get_derivatives)
        if include_noise:
            if get_derivatives and 'noise_deriv' in self.hp:
                k[range(n_data)]+=(np.nan_to_num(np.exp(2*self.hp['noise'].item(0)))+self.corr)
                k[range(n_data,len(k))]+=(np.nan_to_num(np.exp(2*self.hp['noise_deriv'].item(0)))+self.corr)
            else:
                k+=(np.nan_to_num(np.exp(2*self.hp['noise'].item(0)))+self.corr)
        #Calculate predicted variance
        var=(k-np.einsum('ij,ji->i',KQX,cho_solve((self.L,self.low),KQX.T,check_finite=False))).reshape(-1,1)
        var=var*self.delta
        if get_derivatives and self.use_derivatives:
            return var.reshape(n_data,-1,order='F')
        return var
    
    def optimize(self,features,targets,retrain=True,hp=None,prior=None,verbose=False):
        """ Optimize the hyperparameter of the T Process and its kernel
        Parameters:
            features : (N,D) array
                Training features with N data points and D dimensions.
            targets : (N,1) array or (N,D+1) array
                Training targets with or without derivatives with N data points.
            retrain : bool
                Whether to retrain the T Process after the optimization.
            hp : dict
                Use a set of hyperparameters to optimize from else the current set is used.
            maxiter : int
                Maximum number of iterations used by local or global optimization method.
            prior : dict
                A dict of prior distributions for each hyperparameter
            verbose : bool
                Print the optimized hyperparameters and the object function value
        """
        TP=copy.deepcopy(self)
        if not self.use_derivatives:
            targets=targets[:,0:1].copy()
        sol=self.hpfitter.fit(features,targets,TP,hp=hp,prior=prior)
        if verbose:
            print(sol)
        if retrain:
            self.prior=copy.deepcopy(sol['TP'].prior)
            self.set_hyperparams(sol['hp'])
            self.train(features,targets)
        return sol

    def add_regularization(self,K,n_data,overwrite=True):
        "Add the regularization to the diagonal elements of the squared kernel matrix. (K will be overwritten if overwrite=True)"
        #Calculate the correction, so the kernel matrix is invertible
        if not overwrite:
            K=K.copy()
        m_data=len(K)
        self.corr=np.array([self.get_correction(np.diag(K))]).item(0) if self.correction else 0.0
        if 'noise_deriv' in self.hp:
            K[range(n_data),range(n_data)]+=(np.nan_to_num(np.exp(2*self.hp['noise'].item(0)))+self.corr)
            K[range(n_data,m_data),range(n_data,m_data)]+=(np.nan_to_num(np.exp(2*self.hp['noise_deriv'].item(0)))+self.corr)
        else:
            K[range(m_data),range(m_data)]+=(np.nan_to_num(np.exp(2*self.hp['noise'].item(0)))+self.corr)
        return K

    def set_hyperparams(self,new_params):
        """Set or update the hyperparameters for the TP.
            Parameters:
                new_params: dictionary
                    A dictionary of hyperparameters that are added or updated.
            Returns:
                hp : dictionary
                    An updated dictionary of hyperparameters with noise, kernel hyperparameters (like length) 
                    and noise_deriv for the derivative part of the kernel if specified.
        """
        self.hp.update(new_params)
        self.hp=self.kernel.set_hyperparams(self.hp).copy()
        eps_mach=np.sqrt(np.finfo(float).eps)
        # Noise is always in the TP
        if 'noise' not in self.hp:
            self.hp['noise']=np.array([-8.0])
        self.hp['noise']=np.array(self.hp['noise'],dtype=float).reshape(-1)
        if 'noise_deriv' in self.hp:
            self.hp['noise_deriv']=np.array(self.hp['noise_deriv'],dtype=float).reshape(-1)
        return self.hp

    def set_hyperparams(self,new_params):
        """Set or update the hyperparameters for the TP.
            Parameters:
                new_params: dictionary
                    A dictionary of hyperparameters that are added or updated.
            Returns:
                hp : dictionary
                    An updated dictionary of hyperparameters with noise, kernel hyperparameters (like length) 
                    and noise_deriv for the derivative part of the kernel if specified.
        """
        kernel_hp=self.kernel.set_hyperparams(new_params).copy()
        self.hp.update(kernel_hp)
        # Noise is always in the TP
        if 'noise' in new_params:
            self.hp['noise']=np.array(new_params['noise'],dtype=float).reshape(-1)
        elif 'noise' not in self.hp:
            self.hp['noise']=np.array([-8.0])
        if 'noise_deriv' in new_params:
            self.hp['noise_deriv']=np.array(new_params['noise_deriv'],dtype=float).reshape(-1)
        return self.hp

    def set_hpfitter(self,hpfitter):
        " Set the hpfitter "
        self.hpfitter=copy.deepcopy(hpfitter)
        return self
        
    def get_correction(self,K_diag):
        "Get the correction, so that the training covariance matrix is always invertible"
        return (np.sum(K_diag)**2)*(1/(1/(2.3e-16)-(len(K_diag)**2)))

    def get_hyperparameters(self):
        "Get all the hyperparameters"
        return self.hp.copy()

    def get_gradients(self,X,hp,KXX,dis_m=None):
        """Get the gradients of the T Process in respect to the hyperparameters.
            Parameters:
                X : (N,D) array
                    Features with N data points and D dimensions.
                hp : list
                    A list with elements of the hyperparameters that are optimized.
                KXX : (N,N) array
                    The kernel matrix of training data.
                dis_m : (N,N) array (optional)
                    Can be given the distance matrix to avoid recaulcating it.
        """
        hp_deriv={}
        n_data,m_data=len(X),len(KXX)
        if 'noise' in hp:
            if 'noise_deriv' in self.hp:
                hp_deriv['noise']=np.diag(np.array([2*np.exp(2*self.hp['noise'].item(0))]*n_data+[0.0]*(m_data-n_data)).reshape(-1))
            else:
                hp_deriv['noise']=np.diag(np.array([2*np.exp(2*self.hp['noise'].item(0))]*m_data).reshape(-1))
        if 'noise_deriv' in hp:
            hp_deriv['noise_deriv']=np.diag(np.array([0.0]*n_data+[2*np.exp(2*self.hp['noise_deriv'].item(0))]*(m_data-n_data)).reshape(-1))
        hp_deriv |= self.kernel.get_gradients(X,hp,KXX=KXX,dis_m=dis_m)
        return hp_deriv

    def check_attributes(self):
        " Check if all attributes agree between the class and subclasses. "
        if self.use_derivatives!=self.kernel.use_derivatives:
            raise Exception('TP and Kernel do not agree whether to use derivatives!')
        return

    def copy(self):
        " Copy the TP. "
        return copy.deepcopy(self)

    def __repr__(self):
        return f"TProcess(prior={self.prior}, kernel={self.kernel}, hp={self.hp}, use_derivatives={self.use_derivatives}, correction={self.correction})"

