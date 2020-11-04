create table if not exists `userinfo`(
		`userId` BIGINT,
		`id` INT AUTO_INCREMENT,
		`nickname` VARCHAR(50),
		`signature` VARCHAR(512),
		`lasttime` DATETIME,
		PRIMARY KEY(`id`)
		)Engine=Innodb charset=utf8mb4;