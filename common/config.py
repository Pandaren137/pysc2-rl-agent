import json
import numpy as np
from s2clientprotocol import ui_pb2 as sc_ui
from s2clientprotocol import spatial_pb2 as sc_spatial
from pysc2.lib import features
from pysc2.lib.actions import FUNCTIONS, TYPES

CAT = features.FeatureType.CATEGORICAL

# 默认参数
DEFAULT_ARGS = dict(
    screen=0, # converts to (0,0)
    minimap=0,
    screen2=0,
    queued=False,
    control_group_act=sc_ui.ActionControlGroup.Append,
    control_group_id=1,
    select_point_act=sc_spatial.ActionSpatialUnitSelectionPoint.Select,
    select_add=True,
    select_unit_act=sc_ui.ActionMultiPanel.SelectAllOfType,
    select_unit_id=0,
    select_worker=sc_ui.ActionSelectIdleWorker.AddAll,
    build_queue_id=0,
    unload_id=0
)

# 结构化信息
# name => dims
NON_SPATIAL_FEATURES = dict(
    player=(11,),
    game_loop=(1,),
    score_cumulative=(13,),
    available_actions=(len(FUNCTIONS),),
    single_select=(1, 7),
    # multi_select=(0, 7), # TODO
    # cargo=(0, 7), # TODO
    cargo_slots_available=(1,),
    # build_queue=(0, 7), # TODO
    control_groups=(10, 2),
)


class Config:
    # TODO extract embed_dim_fn to config
    def __init__(self, sz, map, run_id, embed_dim_fn=lambda x: max(1, round(np.log2(x)))):
        self.run_id = run_id
        self.sz, self.map = sz, map
        self.embed_dim_fn = embed_dim_fn
        self.feats = self.acts = self.act_args = self.arg_idx = self.ns_idx = None

    def build(self, cfg_path):
        feats, acts, act_args = self._load(cfg_path) # 加载参数，若参数不存在则保存

        if 'screen' not in feats:
            feats['screen'] = features.SCREEN_FEATURES._fields
        if 'minimap' not in feats:
            feats['minimap'] = features.MINIMAP_FEATURES._fields
        if 'non_spatial' not in feats:
            feats['non_spatial'] = NON_SPATIAL_FEATURES.keys()
        self.feats = feats

        # TODO not connected to anything atm
        if acts is None:
            acts = FUNCTIONS
        self.acts = acts

        if act_args is None:
            act_args = TYPES._fields
        self.act_args = act_args

        self.arg_idx = {arg: i for i, arg in enumerate(self.act_args)}
        self.ns_idx = {f: i for i, f in enumerate(self.feats['non_spatial'])}

    def map_id(self):
        return self.map + str(self.sz)

    def full_id(self):
        if self.run_id == -1:
            return self.map_id()
        return self.map_id() + "/" + str(self.run_id)

    def policy_dims(self):
        return [(len(self.acts), 0)] + [(getattr(TYPES, arg).sizes[0], is_spatial(arg)) for arg in self.act_args]

    def screen_dims(self):
        return self._dims('screen')

    def minimap_dims(self):
        return self._dims('minimap')

    def non_spatial_dims(self):
        return [NON_SPATIAL_FEATURES[f] for f in self.feats['non_spatial']]

    # TODO maybe move preprocessing code into separate class?
    def preprocess(self, obs): # 将输入的信息转换为矩阵输入
        return [self._preprocess(obs, _type) for _type in ['screen', 'minimap'] + self.feats['non_spatial']]

    def _dims(self, _type):
        return [f.scale**(f.type == CAT) for f in self._feats(_type)] # 若是分类数据则维度为分类的类别，若是数值数据则是1

    def _feats(self, _type):
        feats = getattr(features, _type.upper() + '_FEATURES') # 获得features.*_FEATURES
        return [getattr(feats, f_name) for f_name in self.feats[_type]] # 获得feats[*]中的数据，子图

    def _preprocess(self, obs, _type):
        if _type in self.feats['non_spatial']:
            return np.array([self._preprocess_non_spatial(ob, _type) for ob in obs])
        spatial = [[ob[_type][f.index] for f in self._feats(_type)] for ob in obs] # 将所有spatial的子图拼在一起
        return np.array(spatial).transpose   ((0, 2, 3, 1))

    def _preprocess_non_spatial(self, ob, _type):
        if _type == 'available_actions':
            acts = np.zeros(len(self.acts))
            acts[ob['available_actions']] = 1
            return acts
        return ob[_type]

    def save(self, cfg_path):
        with open(cfg_path, 'w') as fl:
            json.dump({'feats': self.feats, 'act_args': self.act_args}, fl)

    def _load(self, cfg_path):
        with open(cfg_path, 'r') as fl:
            data = json.load(fl)
        return data.get('feats'), data.get('acts'), data.get('act_args')


def is_spatial(arg):
    return arg in ['screen', 'screen2', 'minimap']
