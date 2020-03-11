from . import consecutive, hitakara, normalexecutor, osakaji, tsuki, freesearch

executors = {
    "common": normalexecutor.CommonBattleExecutor,
    "consecutive": consecutive.ConsecutiveTeamExecutor,
    "hitakara": hitakara.HitakaraBattleExecutor,
    "osakaji": osakaji.OsakajiExecutor,
    "tsuki": tsuki.TsukiExecutor,
    "freesearch": freesearch.FreesearchExecutor,
}


def request(name, api, team, *args, **kwargs):
    if name not in executors:
        raise ValueError(name)

    executor = executors[name]

    return executor(api, team, *args, **kwargs)
