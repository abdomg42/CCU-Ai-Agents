// Contraintes d'unicité sur les entités métiers principales
CREATE CONSTRAINT client_id IF NOT EXISTS
FOR (c:Client) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT subscription_service_id IF NOT EXISTS
FOR (s:Subscription) REQUIRE s.service_id IS UNIQUE;

CREATE CONSTRAINT order_id IF NOT EXISTS
FOR (o:Order) REQUIRE o.id IS UNIQUE;

CREATE CONSTRAINT ticket_id IF NOT EXISTS
FOR (t:Ticket) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT product_id IF NOT EXISTS
FOR (p:Product) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT logevent_id IF NOT EXISTS
FOR (l:LogEvent) REQUIRE l.id IS UNIQUE;

// Index vectoriel sur les embeddings des tickets historiques
CREATE VECTOR INDEX ticket_embeddings IF NOT EXISTS
FOR (t:Ticket) ON (t.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: __VECTOR_DIM__, `vector.similarity_function`: 'cosine'}};
