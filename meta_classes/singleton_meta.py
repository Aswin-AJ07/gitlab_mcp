

class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        # If instance already exists, return it
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance    #ex: singletonmetada._instancees[chilsingletonclass] = childsingletonobj() 
        return cls._instances[cls]
    

