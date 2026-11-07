from config2 import Config


def select_models(task: str):

    return {
        "primary": {
            "provider": Config.PRIMARY_PROVIDER,
            "model": Config.PRIMARY_MODEL
        },

        "fallback": {
            "provider": Config.FALLBACK_PROVIDER,
            "model": Config.FALLBACK_MODEL
        }
    }

#Fun exercise would be make model selector work according to task, so each task has it's own primary and fallback model!!