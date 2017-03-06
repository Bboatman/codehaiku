import requests, json, pickle, copy, math, networkx
import matplotlib.pyplot as plt
from requests.auth import HTTPBasicAuth
from pprint import pprint
from numpy import random
from scipy.spatial import distance
from random import sample 
from collections import defaultdict
from networkx.drawing.nx_pydot import write_dot

patternsHandled = 0
errorsInModel = 0
errorsInSimplifying = 0
alreadySeen = 0
with open("bin/conf.txt", "rb") as file:
	auth = pickle.load(file)
baseUrl = "https://api.ravelry.com"
patternModelFile = "bin/patternModel.txt"
usernameCollectionFile = "bin/usernameCollection.txt"
namingDictionaryFile = "bin/namingDictionary.txt"
usernameCollection = []
patternModel = {}
namingDictionary = {}

#Api Queries
def getUser(username=None):
	url = "/people/%s.json" % username if username else "/current_user.json"
	r = requests.get(baseUrl + url, auth=auth)
	return json.loads(r.text).get("user")

def getFavorites(username):
	url = baseUrl + "/people/%s/favorites/list.json" % username
	r = requests.get(url, auth=auth)
	data = json.loads(r.text).get("favorites")
	favoritesArr = []
	try:
		if data:
			for favorite in data:
				favoritesArr.append(favorite.get("favorited").get("pattern_id"))
	except:
		print("User has no favorites")
	return favoritesArr

def getQueued(username):
	url = baseUrl + "/people/%s/queue/list.json" % username
	r = requests.get(url, auth=auth)
	data = json.loads(r.text).get("queued_project")
	queueArr = []
	try:
		if data:
			for d in data:
				queueArr.append(d.get("pattern_id"))
	except:
		print("User has no queued projects")
	return queueArr

def getProjects(username):
	url = baseUrl + "/projects/%s/list.json" % username
	r = requests.get(url, auth=auth)
	data = json.loads(r.text).get("projects")
	projectArr = []
	try:
		if data:
			for d in data:
				projectArr.append(d.get("pattern_id"))
	except:
		print("User has no projects")
	return projectArr

def getLibrary(username):
	url = baseUrl + "/people/%s/library/search.json" % username
	r = requests.get(url, auth=auth)
	data = json.loads(r.text).get("volumes")
	libArr = []
	try:
		if data:
			for d in data:
				libArr.append(d.get("pattern_id"))
	except:
		print("User library is empty")
	return libArr

def getAuthorPatterns(username):
	url = baseUrl + "/patterns/search.json"
	r = requests.get(url, auth=auth, data={"query":username})
	data = json.loads(r.text).get("patterns")
	patternAr = []
	try:
		if data:
			for d in data:
				patternAr.append(d.get("id"))
	except:
		print("User created no patterns")
	return patternAr

def getPatternForUser(patternId):
	url = baseUrl + "/patterns/%s.json" % patternId
	r = requests.get(url, auth=auth)
	try:
		data = json.loads(r.text).get("pattern")
		userPattern = {"name" : data["name"], 
					   "link": "http://www.ravelry.com/patterns/library/" + data["permalink"]}
		return userPattern
	except:
		print("Bad Data in Request")
		return
	
def getPatternInfo(patternId):
	global patternsHandled
	global patternModel
	global errorsInSimplifying
	global alreadySeen
	global namingDictionary
	modelKeys = list(patternModel.keys())
	if patternId in modelKeys:
		alreadySeen += 1
		return patternModel[patternId]
	else:
		url = baseUrl + "/patterns/%s.json" % patternId
		r = requests.get(url, auth=auth)
		try:
			data = json.loads(r.text).get("pattern")
		except:
			print("Bad Data in Request")
			return
		categoryAr = []
		attributesAr = []
		needlesAr = []
		patternsHandled += 1
		try:
			ndkeys = namingDictionary.keys()
			for category in data.get("pattern_categories"):
				while category:
					catId = str(category.get("id")) + "(category)"
					categoryAr.append(catId)
					if catId not in ndkeys:
						namingDictionary[catId] = category.get("permalink")
					category = category.get("parent")
			for attribute in data.get("pattern_attributes"):
				attrId = str(attribute.get("id")) + "(attribute)"
				if attrId not in ndkeys:
					namingDictionary[attrId] = attribute.get("permalink")
					attributesAr.append(attrId)
			for needle in data.get("pattern_needle_sizes"):
				if needle.get("crochet"):
					needlesAr.append(needle.get("name") + "(crochet)(needle)")
				elif needle.get("knitting"):
					needlesAr.append(needle.get("name") + "(knitting)(needle)")
			craft = str(data.get("craft").get("id")) + "(craft)"
			if craft not in ndkeys:
				namingDictionary[craft] = data.get("craft").get("permalink")
			yarn = "-1(yarn)" if data.get("yarn_weight") is None else str(data.get("yarn_weight").get("id")) + "(yarn)"
			if yarn not in ndkeys:
				namingDictionary[yarn] = "None Listed" if yarn is "-1(yarn)" else data.get("yarn_weight").get("name")
			yardage = "None Listed(yardage)" if data.get("yardage_max") is None else str(data.get("yardage_max")) + "(yardage)"
			price = "0(price)" if data["price"] is None else str(round(data["price"],1)) + "(price)"
			difficulty = str(round(data.get("difficulty_average"),1)) + "(difficulty)"
			rating = str(round(data.get("rating_average"),1)) + "(rating)"
			designers = [x["username"] for x in data["pattern_author"]["users"]]
			pattern = {"id":patternId, "designer_username":designers, "craft":craft,"price":price,"difficulty":difficulty,"yarn":yarn, 
						"yardage":yardage, "rating":rating,	"favorited":data.get("personal_attributes").get("favorited"), 
						"in_library":data.get("personal_attributes").get("in_library"),"queued":data.get("personal_attributes").get("queued"), 
						"attributes":attributesAr, "categories": categoryAr, "needles" : needlesAr}
			updatePatternModel(pattern)
		except:
			print(pattern)
			print("Bad Data in Pattern Manipulation")
			errorsInSimplifying += 1
			return
		return pattern

def getFriends(username):
	url = baseUrl + "/people/%s/friends/list.json" % username
	r = requests.get(url, auth=auth)
	data = json.loads(r.text).get("friendships")
	friendArr = []
	if data:
		for d in data:
			friendArr.append(d.get("friend_username"))
	return friendArr

#Model Generation
def vectorizePattern(pattern):
	vector = []
	for attribute in pattern["attributes"]:
		vector.append((attribute, "attribute", namingDictionary[attribute]))
	for category in pattern["categories"]:
		vector.append((category, "category", namingDictionary[category]))
	for needle in pattern["needles"]:
		vector.append((needle, "needle", needle))
	vector.append((pattern["craft"], "craft", namingDictionary[pattern["craft"]]))
	vector.append((pattern["difficulty"], "difficulty", pattern["difficulty"]))
	vector.append((pattern["price"], "price", pattern["price"]))
	vector.append((pattern["rating"], "rating", pattern["rating"]))
	vector.append((pattern["yardage"], "yardage", pattern["yardage"]))
	vector.append((pattern["yarn"], "yarn", namingDictionary[pattern["yarn"]]))
	return vector

def modifyUserModel(pattern, model, weight):
	global errorsInModel
	modelGraph = model["graph"]
	if pattern is not None:
		m = copy.deepcopy(modelGraph)
		if pattern["id"] not in model["patterns"]:
			model["patterns"].append(pattern["id"])
			nodes = vectorizePattern(pattern)
			nodeComp = copy.deepcopy(nodes)
			size = len(nodeComp) - 1
			index = 0
			while len(nodes) > 0:
				popVal = nodes.pop()
				attrType = popVal[1]
				attr = popVal[0]
				for i in range(index, size):
					nodeData = nodeComp[i][0]
					nodeType = nodeComp[i][1]
					m.add_edge(attr, nodeData)
					try:
						m[attr][nodeData]["weight"] += weight
					except KeyError:
						m[attr][nodeData]["weight"] = weight
						m.node[attr]["color"] = attrType
						m.node[nodeData]["color"] = nodeType

				index += 1
			
			modelGraph = m
		model["graph"] = modelGraph
	return model

def buildUserModel(user, overwrite=False):
	global weights
	username = user.get("username")
	userModel = readUserModel(user, overwrite=overwrite)

	projects = getProjects(username)
	for project in projects:
		pattern = getPatternInfo(project)
		userModel = modifyUserModel(pattern, userModel, weights[3])

	queued = getQueued(username)
	for project in queued:
		pattern = getPatternInfo(project)
		userModel = modifyUserModel(pattern, userModel, weights[2])

	library = getLibrary(username)
	for project in library:
		pattern = getPatternInfo(project)
		userModel = modifyUserModel(pattern, userModel, weights[1])

	favorites = getFavorites(username)
	for project in queued:
		pattern = getPatternInfo(project)
		userModel = modifyUserModel(pattern, userModel, weights[0])

	writeUserModel(user, userModel)
	return userModel

def buildSuggestionList(user, userModel):
	username = user.get("username")
	maxPatternsFromSource = 50

	halfUserPatterns = math.ceil(len(userModel["patterns"]) / 2)
	userPatternSampleSize = halfUserPatterns if halfUserPatterns < maxPatternsFromSource else maxPatternsFromSource	
	patternIdList = sample(userModel["patterns"], userPatternSampleSize)
	
	suggestions = []
	friends = getFriends(username)
	half = math.ceil(len(friends) / 2)
	sampleSize =half if half < len(friends) else len(friends)

	for friend in sample(friends, sampleSize):
		updateUsernameCollection(friend)
		projects = getProjects(friend)
		sampleSize = len(projects) if len(projects) < maxPatternsFromSource else maxPatternsFromSource
		for project in sample(projects,sampleSize):
			suggest = checkForSuggest(project, suggestions)
			if suggest: suggestions.append(suggest)

		favorites = getFavorites(friend)
		sampleSize = len(favorites) if len(favorites) < maxPatternsFromSource else maxPatternsFromSource
		for favorite in sample(favorites,sampleSize):
			suggest = checkForSuggest(favorite, suggestions)
			if suggest: suggestions.append(suggest)

	for patternId in patternIdList:
		pattern = getPatternInfo(patternId)
		designer = pattern["designer_username"]
		updateUsernameCollection(designer)
		designerPatterns = getAuthorPatterns(designer)
		sampleSize = len(designerPatterns) if len(designerPatterns) < maxPatternsFromSource else maxPatternsFromSource
		for patternId in sample(designerPatterns, sampleSize):
			suggest = checkForSuggest(patternId, suggestions)
			if patternId is not None and suggest:
				suggestions.append(patternId)

	modelKeys = patternModel.keys()
	sampleSize = len(modelKeys) if len(modelKeys) < maxPatternsFromSource else maxPatternsFromSource
	for patternId in sample(modelKeys, sampleSize):
		suggest = checkForSuggest(patternId, suggestions)
		if suggest:
			suggestions.append(patternId)

	return suggestions

def checkForSuggest(patternId, suggestionList):
	if patternId not in suggestionList:
		p = getPatternInfo(patternId)
		try:
			if p is not None:
				queued = p.get("queued")
				favorited = p.get("favorited")
				inLibrary = p.get("in_library")
				if not queued or favorited or inLibrary:
					return patternId
		except:
			print("Bad Pattern")
			pprint(p)


# Tools
def logNormalRandomizedWeighting():
	distribution = random.lognormal(1.6, .1, 4)
	s = sorted(distribution.tolist(), reverse=True)
	if s[3] > 2:
		diff = 2 - s[3]
		return [round(x + diff,3) for x in s]
	return [round(x,3) for x in s]

def readUsernameCollection():
	global usernameCollection
	filename = usernameCollectionFile
	try:
		with open(filename, "rb") as file:
			usernameCollection = pickle.load(file)
		print("Read in Username Collection")
	except:
		print("Malformated Username File")
		usernameCollection = []

def readPatternModel():
	global patternModel
	filename = patternModelFile
	try:
		with open(filename, "rb") as file:
			patternModel = pickle.load(file)
		print("Read in Pattern Models")
	except:
		print("Malformated Pattern File")
		patternModel = defaultdict(dict)

def updatePatternModel(pattern):
	if not any(pattern.get("id") == s for s in patternModel.keys()):
		if pattern is not None:
			patternModel[pattern.get("id")] = pattern

def updateUsernameCollection(username):
	if type(username) is list:
		for user in username:
			if user not in usernameCollection and user is not None:
					usernameCollection.append(user)
	elif type(username) is str:
		if username not in usernameCollection and username is not None:
					usernameCollection.append(username)

def saveModels():
	global usernameCollection
	global patternModel
	global namingDictionary

	with open(patternModelFile, "wb") as file:
		pickle.dump(patternModel, file)

	with open(usernameCollectionFile, "wb") as file:
		pickle.dump(usernameCollection, file)

	with open(namingDictionaryFile, "wb") as file:
		pickle.dump(namingDictionary, file)

def readUserModel(user, overwrite=False):
	userId = user.get("id")
	filename = "bin/%s.txt" % userId
	if overwrite:
		userModel = {"patterns": [], "graph":networkx.Graph()}
		print("New Model for User %s" % user.get("username"))
		return userModel
	try:
		with open(filename, "rb") as file:
			userModel = pickle.load(file)
		print("Read in Model for User %s" % user.get("username"))
		return userModel
	except:
		print("Nonexistant/Malformed File")
		userModel = {"patterns": [], "graph":networkx.Graph()}
		print("New Model for User %s" % user.get("username"))
		return userModel

def writeUserModel(user, userModel):
	userId = user.get("id")
	filename = "bin/%s.txt" % userId
	with open(filename, "wb") as file:
		pickle.dump(userModel, file)

def readNamingDictionary():
	global namingDictionary
	filename = namingDictionaryFile
	try:
		with open(filename, "rb") as file:
			namingDictionary = pickle.load(file)
		print("Read in Naming Dictionary")
	except:
		print("Nonexistant Naming Dictionary")
		print("New Naming Dict")
		namingDictionary = defaultdict(str)

def centralityManipulation(centralityResult):
	centralityList = sorted([(k, centralityResult[k]) for k in centralityResult.keys()], key=lambda x: x[1], reverse=True)
	adjustment = 1 / centralityList[0][1]
	adjustedCentrality = [(k[0], k[1] * adjustment) for k in centralityList]
	print("Adjustment", adjustment)
	return adjustedCentrality

def solveUserCentrality(usermodel, current_user):
	closennessPlusCentrality = centralityManipulation(networkx.current_flow_closeness_centrality(usermodel["graph"]))
	networkx.write_graphml(usermodel["graph"], "bin/%s.graphml" % current_user["username"])
	return closennessPlusCentrality

def comparePatternToUser(centralityVector, patternId):
	pattern = getPatternInfo(patternId)
	pattern_attributes, attrType, attrName = zip(*vectorizePattern(pattern))
	inUser, centralityVals = zip(*centralityVector)
	userVector = [attr[1] for attr in centralityVector if attr[0] in pattern_attributes]
	for attribute in pattern_attributes:
		if attribute not in inUser:
			userVector.append(0)

	patternVector = [1 for x in range(len(userVector))]
	cosineSim = distance.cosine(userVector, patternVector)
	return cosineSim

def mapAttributeToName(attributeList):
	global namingDictionary
	nameMapped = []
	for x in adjustedCentrality:
		if x[0] in namingDictionary.keys():
			nameMapped.append((namingDictionary[x[0]], x[1]))
		else: 
			nameMapped.append((x[0], x[1]))
	return nameMapped

def run():
	global weights
	weights = logNormalRandomizedWeighting()
	readPatternModel()
	readUsernameCollection()
	readNamingDictionary()
	#random_user = sample(usernameCollection, 1)[0]
	current_user = getUser()#random_user)
	usermodel = buildUserModel(current_user)
	print("User Model Built")
	adjustedCentrality = solveUserCentrality(usermodel, current_user)
	print("Centrality of Model Found")
	suggestionList = buildSuggestionList(current_user, usermodel)
	print("Suggestion List Built")
	suggestionsRecommended = []
	for suggestion in suggestionList:
		sim = comparePatternToUser(adjustedCentrality, suggestion)
		suggestionsRecommended.append((suggestion, sim))
	weightedSuggestions = sorted(suggestionsRecommended, key=lambda x: x[1], reverse=True)
	suggestionsToLookAt = []
	for pattern in weightedSuggestions[:20]:
		patternId = pattern[0]
		suggestionsToLookAt.append(getPatternForUser(patternId))
	pprint(suggestionsToLookAt)
	saveModels()	
run()