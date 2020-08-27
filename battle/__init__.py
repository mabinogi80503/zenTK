from . import (
    armament,
    consecutive,
    hitakara,
    normalexecutor,
    osakaji,
    tsuki,
    freesearch,
    firework_retake,
)

executors = {
    "common": normalexecutor.CommonBattleExecutor,
    "consecutive": consecutive.ConsecutiveTeamExecutor,
    "hitakara": hitakara.HitakaraBattleExecutor,
    "osakaji": osakaji.OsakajiExecutor,
    "tsuki": tsuki.TsukiExecutor,
    "freesearch": freesearch.FreesearchExecutor,
    "armament": armament.ArmamentExpansionExecutor,
    "firework": firework_retake.FireworkRetakeExecutor,
}


def request(name, api, team, *args, **kwargs):
    if name not in executors:
        raise ValueError(name)

    executor = executors[name]

    return executor(api, team, *args, **kwargs)
