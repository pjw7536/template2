-- 운영 migration이 사용하는 trigram GIN operator class를 테스트 DB에도 제공합니다.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Django가 생성하는 test database의 기본 template에도 같은 extension을 둡니다.
\connect template1
CREATE EXTENSION IF NOT EXISTS pg_trgm;
