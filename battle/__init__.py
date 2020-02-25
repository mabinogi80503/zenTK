from . import consecutive, hitakara, normalexecutor, osakaji, tsuki

executors = {
    "common": normalexecutor.CommonBattleExecutor,
    "consecutive": consecutive.ConsecutiveTeamExecutor,
    "hitakara": hitakara.HitakaraBattleExecutor,
    "osakaji": osakaji.OsakajiExecutor,
    "tsuki": tsuki.TsukiExecutor,
}


def request(name, api, team, *args, **kwargs):
    if name not in executors:
        raise ValueError(name)

    executor = executors[name]

    return executor(api, team, *args, **kwargs)
