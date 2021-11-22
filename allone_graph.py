#import numpy as np
from omegaconf.dictconfig import DictConfig 
from omegaconf import OmegaConf 
#import plotly.express as px
#from plotly.express import data
import plotly.graph_objects as go
import json
import pdb
from itertools import islice
import glob
import logging
import os
from scipy.stats.mstats import gmean
import pandas as pd
from itertools import islice

cache_list = ["rand_cache=base-random-rp,script=run-sample",
    "rand_cache=ceaser-1-random-rp,script=run-sample",
    "rand_cache=ceaser-2-random-rp,script=run-sample",
    "rand_cache=ceaser-4-random-rp,script=run-sample",
    "rand_cache=ceaser-16-random-rp,script=run-sample"
]

project_name = ["base-random-rp", "ceaser-1-random-rp", "ceaser-2-random-rp", "ceaser-4-random-rp", "ceaser-16-random-rp"]
stat_list = ["samples.avg.core-ipc.avg", "samples.avg.llc-miss-rate", "samples.avg.branch-mispredict-rate.avg", "samples.avg.llc-mpki"]
col_list = ["benchmark",
        "project",
        "samples.avg.core-ipc.avg",
        "samples.avg.llc-miss-rate",
        "samples.avg.branch-mispredict-rate.avg",
        "samples.avg.llc-mpki"
]

def get_plots(cache_list): 
    configure = ".hydra/config.yaml"
    path1 = "/data/home/apps/spark-experiments/outputs/+project"
    path2 = "suite=specrate2017/benchmark=*/*" 
    benchmarks_tested = []
    list_of_path_lists = []
    for each_cache in cache_list:
        list_of_path_lists.append(glob.glob(os.path.join(path1, each_cache, path2))) #sublists inside benchmark_list which has the path to each benchmark inside each cache_config
    num_benchmarks = len(list_of_path_lists[0]) #is 22
    row_list = []
    for i in range(num_benchmarks):
        hold_paths = []
        for j in range(len(cache_list)): #should be 0,1,2,3,4 bc 5 cache configs
            hold_paths.append(list_of_path_lists[j][i])
        for ind in range(len(cache_list)): #should put 5 cfg dictionaries on list
            checker = os.path.join(hold_paths[ind], "rollup.json") 
            if len(glob.glob(checker)) == 0: #checks json file actually exists
                continue
            elif os.path.getsize(checker) == 2: #if json file is empty
                continue
            else:
                with open(os.path.join(hold_paths[ind], "rollup.json")) as f:
                    dic = json.load(f)
            c = OmegaConf.load(os.path.join(hold_paths[ind], configure))
            benchmark = c.benchmark.name
            project = c.project.experiment
            benchmarks_tested = c.benchmark.benchmarks
            data_list = []
            temp_list = []
            for solo_stat in stat_list:
                data_list.append(dic.get(solo_stat))
            temp_list = [benchmark] + [project] + data_list
            row_list.append(temp_list)
    df = pd.DataFrame(data = row_list, columns=col_list)

    benchmarks_tested = sorted(benchmarks_tested)
    x_graph = benchmarks_tested.copy()
    x_graph.append("geometric-mean")
    fig = go.Figure()

    for stat in stat_list: 
        list_of_y_list = []
        for project in project_name:
            y_list = []
            for benchmark in benchmarks_tested:
                sub_df = df[(df['benchmark'] == benchmark) & (df['project']==project)]
                if sub_df.empty:
                    continue
                wanted_stat = sub_df.iloc[0][stat]
                y_list.append(wanted_stat)
            list_of_y_list.append(y_list)
            print(list_of_y_list)

        for y in range(len(list_of_y_list)):
            temp = gmean(list_of_y_list[y])
            list_of_y_list[y].append(temp) 

        for x in range(len(project_name)):   
            fig.add_trace(go.Bar(name = project_name[x], y=list_of_y_list[x], x=x_graph))
        fig.update_layout(barmode='group', title_text = (f"For {stat}"))
        fig.write_image(f"results/new_results/{stat}.pdf")
        fig.data = []

if __name__ == "__main__":
    get_plots(cache_list)


