#!/usr/bin/env python3
"""Factories ONLY for development-fold model pipelines; no final-test access.

For each temporal train/validation fold instantiate a *new* Pipeline. All
quantiles, medians, robust scaling and estimator coefficients are fitted on
that fold's TRAIN segment only. Choose clipping/no clipping using development
validation, then freeze this choice before the single final test.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

CONTINUOUS = [
    'log_assets','equity_to_assets','asset_log_growth_1q','asset_log_growth_4q',
    'nclnls_to_loans','loan_allowance_to_loans','cash_to_assets',
    'cash_and_securities_to_assets','deposits_to_assets','net_loans_to_assets',
    'roa_reported_percent','nimy_reported_percent',
]
BINARY=['negative_equity_flag','loss_flag_roa_negative','loan_denominator_invalid_flag']
FEATURES=CONTINUOUS+BINARY

class TrainOnlyQuantileClipper(BaseEstimator, TransformerMixin):
    """Clip using quantiles fitted on training, ignoring missing values."""
    def __init__(self, lower=0.01, upper=0.99):
        self.lower=lower
        self.upper=upper

    def fit(self,X,y=None):
        if not 0 <= self.lower < self.upper <= 1:
            raise ValueError('Require 0 <= lower < upper <=1')
        v=np.asarray(X,dtype=np.float64)
        if v.ndim!=2:raise ValueError('Expected 2-D array')
        if np.isinf(v).any():raise ValueError('Infinity values must be converted to missing upstream')
        self.lower_=np.full(v.shape[1],-np.inf)
        self.upper_=np.full(v.shape[1],np.inf)
        for j in range(v.shape[1]):
            z=v[np.isfinite(v[:,j]),j]
            if len(z):
                self.lower_[j]=np.quantile(z,self.lower)
                self.upper_[j]=np.quantile(z,self.upper)
        self.n_features_in_=v.shape[1]
        return self

    def transform(self,X):
        v=np.asarray(X,dtype=np.float64)
        if v.ndim!=2 or v.shape[1]!=self.n_features_in_:
            raise ValueError('Feature width differs from fitted training data')
        return np.clip(v,self.lower_,self.upper_)

class AllMissingFlags(BaseEstimator,TransformerMixin):
    """Fixed one-per-column missingness flags, including all-zero columns."""
    def fit(self,X,y=None):
        self.n_features_in_=np.asarray(X).shape[1]
        return self
    def transform(self,X):
        v=np.asarray(X,dtype=np.float64)
        if v.ndim!=2 or v.shape[1]!=self.n_features_in_:
            raise ValueError('Feature width mismatch')
        return np.isnan(v).astype(np.float64)


def make_preprocessor(clip=True,lower=0.01,upper=0.99):
    continuous_steps=[]
    if clip:
        continuous_steps.append(('training_quantile_clip',TrainOnlyQuantileClipper(lower,upper)))
    continuous_steps.extend([
        ('training_median',SimpleImputer(strategy='median',keep_empty_features=True)),
        ('training_robust_scale',RobustScaler()),
    ])
    return ColumnTransformer([
        ('continuous',Pipeline(continuous_steps),CONTINUOUS),
        ('binary',SimpleImputer(strategy='constant',fill_value=0,keep_empty_features=True),BINARY),
        ('missing',AllMissingFlags(),FEATURES),
    ],remainder='drop',sparse_threshold=0)


def make_logistic_pipeline(clip=True,lower=0.01,upper=0.99,C=1.0,seed=2026):
    return Pipeline([
        ('prep',make_preprocessor(clip,lower,upper)),
        ('model',LogisticRegression(C=C,max_iter=1500,random_state=seed,class_weight='balanced')),
    ])


def _self_test():
    import pandas as pd
    a=np.array([1.,2.,3.,4.,5.,np.nan])
    train=pd.DataFrame({f:a for f in CONTINUOUS})
    for b in BINARY:train[b]=[0.,1.,0.,1.,0.,np.nan]
    val=train.head(2).copy()
    val.loc[val.index[0],'log_assets']=1e12
    tx=make_preprocessor(clip=True)
    ztr=tx.fit_transform(train)
    q_before=tx.named_transformers_['continuous'].named_steps['training_quantile_clip'].upper_.copy()
    zval=tx.transform(val)
    q_after=tx.named_transformers_['continuous'].named_steps['training_quantile_clip'].upper_.copy()
    assert ztr.shape[1]==30 and zval.shape[1]==30
    assert np.array_equal(q_before,q_after)
    assert zval[0,0] <= max(ztr[:,0])+1e-10
    print('PIPELINE SYNTHETIC TEST PASS: 30 columns; validation outlier does not change trained quantiles.')


if __name__=='__main__':_self_test()
