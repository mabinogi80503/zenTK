from copy import copy


class event_find_path:
    def __init__(self):
        self.actual_path = [
            [2],
            [3, 4, 5],
            [2, 4, 6, 7],
            [2, 3, 5, 8],
            [2, 4, 9],
            [3, 7, 11],
            [3, 6, 8, 12],
            [4, 7, 9, 17],
            [5, 8, 10, 13],
            [9, 14, 15],
            [6, 12, 16],
            [7, 11, 17],
            [9, 14, 17, 18],
            [10, 13, 19],
            [10, 19],
            [11, 17],
            [8, 12, 13, 16, 18, 20],
            [13, 17, 19],
            [14, 15, 18],
            [17],
        ]

        self.target = 20
        self.trace = []

    def prepare_path(self, trace):
        self.trace = trace
        self.best_path = []
        self.process = []
        self.solution = []

    def add_next_step(self, vec):
        node = vec[-1]
        for i in self.actual_path[node - 1]:
            temp = copy(vec)
            temp.append(i)

            if i == self.target:
                self.solution.append(temp)
            else:
                self.process.append(temp)

    def search_path(self, start, step):
        self.process.append([start])
        for i in range(1, step + 1):
            while len(self.process[0]) <= i:
                self.add_next_step(self.process.pop(0))

    def score(self, vec):
        score = len(set(vec)) - 1
        for i in vec:
            if i in set(self.trace):
                score = score - 1
        return score

    def find_best_path(self):
        max_score = -1
        while self.solution:
            vec = self.solution.pop(0)
            if self.score(vec) >= max_score:
                self.best_path = copy(vec)
                max_score = self.score(vec)

    def find_next_node(self, start, step, trace):
        self.prepare_path(trace)
        self.search_path(start, step)
        self.find_best_path()
        if self.best_path:
            return self.best_path[1]
        else:
            return -1

